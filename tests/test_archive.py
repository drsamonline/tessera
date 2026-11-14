import json
import os
import shutil
import tempfile
import unittest

from tessera import archive, canonical, ledger

TENANT = "018f0000-0000-7000-8000-000000000001"
REF = "Contact:018f0000-0000-7000-8000-00000000c001"
OTHER_REF = "Contact:018f0000-0000-7000-8000-00000000c002"


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-archive-")
        self.segments = os.path.join(self.dir, "segments")
        self.log = ledger.EventLog(os.path.join(self.dir, "ledger.jsonl"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, count=10, ref=REF):
        for index in range(count):
            self.log.append(TENANT, "system", "contact.sync",
                            {"record": {"n": index}}, canonical_ref=ref,
                            source_node_id="hubspot")


class TestArchive(Case):
    def test_a_segment_is_written_with_a_manifest(self):
        self.write(10)
        manifest = archive.archive(self.log, TENANT, self.segments, 6)
        self.assertEqual(manifest["count"], 6)
        self.assertEqual(manifest["first_sequence"], 1)
        self.assertEqual(manifest["last_sequence"], 6)
        self.assertTrue(os.path.exists(os.path.join(self.segments, manifest["segment"])))

    def test_archiving_removes_nothing(self):
        self.write(10)
        before = len(list(self.log.events(TENANT)))
        archive.archive(self.log, TENANT, self.segments, 6)
        self.assertEqual(len(list(self.log.events(TENANT))), before,
                         "archiving is a copy, not a move")

    def test_a_segment_verifies_on_its_own(self):
        self.write(10)
        manifest = archive.archive(self.log, TENANT, self.segments, 6)
        path = os.path.join(self.segments, manifest["segment"])
        ok, problems = archive.verify_segment(path)
        self.assertTrue(ok, problems)

    def test_a_tampered_segment_fails(self):
        self.write(10)
        manifest = archive.archive(self.log, TENANT, self.segments, 6)
        path = os.path.join(self.segments, manifest["segment"])
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
        lines[2] = lines[2].replace('{"n":2}', '{"n":99}')
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
        ok, problems = archive.verify_segment(path)
        self.assertFalse(ok)
        self.assertTrue(any("hash mismatch" in p or "manifest" in p for p in problems))

    def test_a_tampered_manifest_fails(self):
        self.write(10)
        manifest = archive.archive(self.log, TENANT, self.segments, 6)
        path = os.path.join(self.segments, manifest["segment"]).replace(
            ".jsonl", ".manifest.json")
        with open(path, encoding="utf-8") as handle:
            blob = json.load(handle)
        blob["count"] = 999
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(blob, handle)
        ok, problems = archive.verify_segment(path.replace(".manifest.json", ".jsonl"))
        self.assertFalse(ok)
        self.assertTrue(any("checksum" in p for p in problems))

    def test_a_missing_manifest_is_reported(self):
        self.write(3)
        manifest = archive.archive(self.log, TENANT, self.segments, 3)
        path = os.path.join(self.segments, manifest["segment"])
        os.remove(path.replace(".jsonl", ".manifest.json"))
        ok, problems = archive.verify_segment(path)
        self.assertFalse(ok)
        self.assertTrue(any("no manifest" in p for p in problems))

    def test_archiving_nothing_is_refused(self):
        self.write(3)
        with self.assertRaises(archive.ArchiveError):
            archive.archive(self.log, TENANT, self.segments, 0)


class TestCompact(Case):
    def test_compaction_shrinks_the_live_log_and_keeps_it_verifiable(self):
        self.write(20)
        result = archive.compact(self.log, TENANT, self.segments, 15)
        self.assertEqual(result["archived"], 15)

        live = list(self.log.events(TENANT))
        self.assertEqual(len(live), 5, "the five events after the cut")
        self.assertIn(TENANT, self.log.header(), "the compacted log carries a header")

        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)

    def test_the_marker_links_to_the_archived_tail(self):
        self.write(20)
        before = [event for event in self.log.events(TENANT)][14]
        result = archive.compact(self.log, TENANT, self.segments, 15)
        header = self.log.header()[TENANT]
        self.assertEqual(header["archived_tail"], before["hash"],
                         "the compacted chain links to the archived one by arithmetic")
        self.assertEqual(header["archived_through"], 15)
        self.assertEqual(result["archived_through"], 15)

    def test_the_segment_still_verifies_after_compaction(self):
        self.write(20)
        result = archive.compact(self.log, TENANT, self.segments, 15)
        path = os.path.join(self.segments, result["segment"])
        ok, problems = archive.verify_segment(path)
        self.assertTrue(ok, problems)

    def test_new_events_after_compaction_still_chain(self):
        self.write(20)
        archive.compact(self.log, TENANT, self.segments, 15)
        self.write(5)
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)
        sequences = [event["sequence"] for event in self.log.events(TENANT)]
        self.assertEqual(sequences, list(range(16, 26)))

    def test_a_second_compaction_is_sound(self):
        self.write(30)
        archive.compact(self.log, TENANT, self.segments, 10)
        archive.compact(self.log, TENANT, self.segments, 25)
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)
        self.assertEqual(self.log.header()[TENANT]["archived_through"], 25)

    def test_the_history_of_a_record_spans_both_halves(self):
        self.write(5, ref=REF)
        self.write(5, ref=OTHER_REF)
        archive.compact(self.log, TENANT, self.segments, 7)
        history = archive.history(self.log, TENANT, REF, self.segments)
        self.assertEqual(len(history), 5, "the caller should not know which half")
        self.assertEqual([event["sequence"] for event in history], [1, 2, 3, 4, 5])

    def test_history_is_ordered_across_the_seam(self):
        self.write(10, ref=REF)
        archive.compact(self.log, TENANT, self.segments, 4)
        history = archive.history(self.log, TENANT, REF, self.segments)
        sequences = [event["sequence"] for event in history]
        self.assertEqual(sequences, sorted(sequences))

    def test_the_compaction_leaves_a_trace(self):
        self.write(10)
        archive.compact(self.log, TENANT, self.segments, 5)
        header = self.log.header()[TENANT]
        self.assertEqual(header["archived_count"], 5,
                         "a compaction that leaves no trace is a deletion")
        self.assertEqual(header["segment"], "segment-000001-000005.jsonl")

    def test_an_incremental_projection_reads_a_compacted_log(self):
        from tessera import projection
        self.write(10)
        archive.compact(self.log, TENANT, self.segments, 5)
        live = projection.Projection(self.log, TENANT, incremental=True)
        self.assertEqual(live.refresh(), 5,
                         "a header line must not be handed to the projection")

    def test_verify_still_catches_tampering_after_compaction(self):
        self.write(20)
        archive.compact(self.log, TENANT, self.segments, 15)
        with open(self.log.path, encoding="utf-8") as handle:
            lines = handle.readlines()
        lines[-1] = lines[-1].replace('{"n":19}', '{"n":0}')
        with open(self.log.path, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
        ok, _ = self.log.verify()
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
