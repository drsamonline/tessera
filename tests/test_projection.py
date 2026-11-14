import os
import shutil
import tempfile
import unittest

from tessera import canonical
from tessera.checkpoint import Checkpointer
from tessera.ledger import EventLog
from tessera.mirror import MarkdownMirror
from tessera.projection import Projection

TENANT = "018f0000-0000-7000-8000-000000000001"
CONTACT = "018f0000-0000-7000-8000-00000000c001"
REF = "Contact:" + CONTACT


def contact(**over):
    payload = {
        "id": CONTACT, "tenant_id": TENANT,
        "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted", "lawful_basis": "consent",
        "purpose_id": "p", "retention_policy_id": "r",
        "full_name": "Asha Rao", "email": "asha@example.com",
    }
    payload.update(over)
    return payload


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-proj-")
        self.log = EventLog(os.path.join(self.dir, "ledger.jsonl"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, record, at="2026-11-01T09:00:00Z", actor="system"):
        return self.log.append(TENANT, actor, "contact.sync", {"record": record},
                               canonical_ref=REF, source_node_id="hubspot",
                               timestamp=at)


class TestProjection(Case):
    def test_state_reflects_the_last_record(self):
        self.write(contact())
        projection = Projection(self.log, TENANT).build()
        self.assertEqual(projection.get("Contact", CONTACT)["email"], "asha@example.com")
        self.assertEqual(projection.count("Contact"), 1)

    def test_a_later_record_wins(self):
        self.write(contact(), at="2026-11-01T09:00:00Z")
        self.write(contact(email="new@example.com"), at="2026-11-02T09:00:00Z")
        projection = Projection(self.log, TENANT).build()
        self.assertEqual(projection.get("Contact", CONTACT)["email"], "new@example.com")

    def test_a_field_patch_is_applied(self):
        self.write(contact())
        self.log.append(TENANT, "human", "contact.email.write",
                        {"field": "email", "value": "patched@example.com", "node": "hubspot"},
                        canonical_ref=REF, source_node_id="hubspot",
                        timestamp="2026-11-03T09:00:00Z")
        projection = Projection(self.log, TENANT).build()
        self.assertEqual(projection.get("Contact", CONTACT)["email"], "patched@example.com")

    def test_events_without_data_are_skipped_not_guessed(self):
        self.write(contact())
        self.log.append(TENANT, "system", "conflict.resolved",
                        {"field": "email", "rule": "authority_map", "winner": "hubspot"},
                        canonical_ref=REF, source_node_id="hubspot")
        projection = Projection(self.log, TENANT).build()
        self.assertEqual(projection.skipped, 1)
        self.assertEqual(projection.applied, 1)

    def test_as_of_answers_what_we_knew(self):
        self.write(contact(), at="2026-11-01T09:00:00Z")
        self.write(contact(email="new@example.com"), at="2026-11-05T09:00:00Z")
        projection = Projection(self.log, TENANT).build()
        self.assertEqual(
            projection.as_of("Contact", CONTACT, "2026-11-02T00:00:00Z")["email"],
            "asha@example.com")
        self.assertEqual(
            projection.as_of("Contact", CONTACT, "2026-11-06T00:00:00Z")["email"],
            "new@example.com")

    def test_valid_at_answers_what_was_true(self):
        self.write(contact(email="a@example.com", valid_from="2026-11-01T00:00:00Z"),
                   at="2026-11-01T09:00:00Z")
        # a correction that arrives late, with a valid time in the past
        self.write(contact(email="b@example.com", valid_from="2026-11-03T00:00:00Z"),
                   at="2026-11-10T09:00:00Z")
        projection = Projection(self.log, TENANT).build()
        self.assertEqual(
            projection.valid_at("Contact", CONTACT, "2026-11-02T00:00:00Z")["email"],
            "a@example.com")
        self.assertEqual(
            projection.valid_at("Contact", CONTACT, "2026-11-04T00:00:00Z")["email"],
            "b@example.com")

    def test_rebuildable(self):
        for i in range(5):
            self.write(contact(email=f"{i}@example.com"), at=f"2026-11-0{i + 1}T09:00:00Z")
        projection = Projection(self.log, TENANT).build()
        result = projection.verify_rebuildable()
        self.assertTrue(result["rebuildable"], result)
        self.assertEqual(result["live_fingerprint"], result["rebuilt_fingerprint"])

    def test_a_tampered_projection_is_not_rebuildable(self):
        self.write(contact())
        projection = Projection(self.log, TENANT).build()
        projection.state["Contact"][CONTACT]["email"] = "tampered@example.com"
        self.assertFalse(projection.verify_rebuildable()["rebuildable"])


class TestCheckpoint(Case):
    def setUp(self):
        super().setUp()
        self.path = os.path.join(self.dir, "checkpoints.jsonl")
        self.cp = Checkpointer(self.log, TENANT, self.path, every=1)

    def test_write_and_verify(self):
        self.write(contact())
        row = self.cp.write()
        self.assertIsNotNone(row)
        self.assertEqual(row["sequence"], 1)
        ok, problems = self.cp.verify()
        self.assertTrue(ok, problems)

    def test_first_checkpoint_is_the_base(self):
        cp = Checkpointer(self.log, TENANT, self.path, every=3)
        self.write(contact())
        self.assertIsNotNone(cp.write(), "the first checkpoint has nothing to diff from")

    def test_threshold_is_respected_after_the_base(self):
        cp = Checkpointer(self.log, TENANT, self.path, every=3)
        self.write(contact())
        cp.write()
        self.write(contact(email="b@example.com"))
        self.assertIsNone(cp.write(), "one more event is below the threshold of three")
        self.write(contact(email="c@example.com"))
        self.write(contact(email="d@example.com"))
        self.assertIsNotNone(cp.write(), "three more events reach the threshold")
        self.assertEqual(len(cp.checkpoints()), 2)

    def test_chain_links(self):
        self.write(contact())
        first = self.cp.write()
        self.write(contact(email="b@example.com"))
        second = self.cp.write()
        self.assertEqual(second["parent"], first["hash"])
        ok, problems = self.cp.verify()
        self.assertTrue(ok, problems)

    def test_a_tampered_checkpoint_fails_verification(self):
        self.write(contact())
        self.cp.write()
        rows = self.cp.checkpoints()
        rows[0]["state"]["Contact"][CONTACT]["email"] = "tampered@example.com"
        with open(self.path, "w", encoding="utf-8") as f:
            import json
            f.write(json.dumps(rows[0]) + "\n")
        ok, problems = self.cp.verify()
        self.assertFalse(ok)

    def test_diff_reports_changed_fields(self):
        self.write(contact())
        self.cp.write()
        self.write(contact(email="changed@example.com", full_name="Asha R Rao"))
        self.cp.write()
        diff = self.cp.diff(0, 1)
        self.assertIn("email", diff["changed"][REF])
        self.assertIn("full_name", diff["changed"][REF])
        self.assertEqual(diff["added"], [])

    def test_revert_appends_and_never_deletes(self):
        self.write(contact())
        self.cp.write()
        self.write(contact(email="wrong@example.com"))
        before = sum(1 for _ in self.log.events())

        result = self.cp.revert_to(0)
        after = sum(1 for _ in self.log.events())

        self.assertEqual(result["restored"], 1)
        self.assertGreater(after, before, "a revert appends events")
        projection = Projection(self.log, TENANT).build()
        self.assertEqual(projection.get("Contact", CONTACT)["email"], "asha@example.com")

    def test_the_ledger_still_verifies_after_a_revert(self):
        self.write(contact())
        self.cp.write()
        self.write(contact(email="wrong@example.com"))
        self.cp.revert_to(0)
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)


class TestMirror(Case):
    def setUp(self):
        super().setUp()
        self.out = os.path.join(self.dir, "mirror")
        self.mirror = MarkdownMirror(self.log, TENANT, self.out)

    def test_writes_one_file_per_record(self):
        self.write(contact())
        result = self.mirror.mirror()
        self.assertEqual(result["files"], 1)
        path = self.mirror.path_for("Contact", CONTACT)
        self.assertTrue(os.path.exists(path))

    def test_file_contains_fields_and_history(self):
        self.write(contact())
        self.mirror.mirror()
        with open(self.mirror.path_for("Contact", CONTACT), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("asha@example.com", text)
        self.assertIn("## History", text)
        self.assertIn("contact.sync", text)

    def test_manifest_records_the_sequence(self):
        self.write(contact())
        self.mirror.mirror()
        manifest = self.mirror.manifest()
        self.assertEqual(manifest["sequence"], 1)
        self.assertIn(REF, manifest["files"])

    def test_lag_counts_events_since_the_last_run(self):
        self.write(contact())
        self.mirror.mirror()
        self.assertEqual(self.mirror.lag_events(), 0)
        self.write(contact(email="b@example.com"))
        self.assertEqual(self.mirror.lag_events(), 1)

    def test_verify_detects_a_hand_edited_file(self):
        self.write(contact())
        self.mirror.mirror()
        path = self.mirror.path_for("Contact", CONTACT)
        with open(path, "a", encoding="utf-8") as f:
            f.write("\nedited by hand\n")
        result = self.mirror.verify()
        self.assertFalse(result["ok"])
        self.assertIn(REF, result["changed"])

    def test_mirror_is_rebuildable(self):
        self.write(contact())
        self.mirror.mirror()
        first = self.mirror.manifest()["files"][REF]
        shutil.rmtree(self.out)
        self.mirror.mirror()
        self.assertEqual(self.mirror.manifest()["files"][REF], first,
                         "the same ledger must produce the same bytes")


if __name__ == "__main__":
    unittest.main()
