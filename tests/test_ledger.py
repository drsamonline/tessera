import json
import os
import tempfile
import unittest

from tessera import canonical, ledger

TENANT = "018f0000-0000-7000-8000-000000000001"
OTHER = "018f0000-0000-7000-8000-000000000002"
NODE_A = "018f0000-0000-7000-8000-0000000000a1"
NODE_B = "018f0000-0000-7000-8000-0000000000a2"
REF = "Contact:018f0000-0000-7000-8000-00000000c001"


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-test-")
        self.path = os.path.join(self.dir, "ledger.jsonl")
        self.log = ledger.EventLog(self.path)

    def tearDown(self):
        for name in os.listdir(self.dir):
            os.unlink(os.path.join(self.dir, name))
        os.rmdir(self.dir)

    def append(self, **kw):
        kw.setdefault("tenant_id", TENANT)
        kw.setdefault("actor", "system")
        kw.setdefault("action", "contact.upsert")
        kw.setdefault("payload", {"email": "asha@example.com"})
        kw.setdefault("canonical_ref", REF)
        kw.setdefault("source_node_id", NODE_A)
        return self.log.append(**kw)


class TestAppend(LedgerCase):
    def test_first_event_links_to_genesis(self):
        event = self.append()
        self.assertEqual(event["prev_event_hash"], ledger.GENESIS)
        self.assertEqual(event["sequence"], 1)
        self.assertEqual(len(event["hash"]), 64)

    def test_second_event_links_to_first(self):
        first = self.append()
        second = self.append()
        self.assertEqual(second["prev_event_hash"], first["hash"])
        self.assertEqual(second["sequence"], 2)

    def test_chains_are_independent_per_tenant(self):
        a1 = self.append()
        b1 = self.append(tenant_id=OTHER)
        a2 = self.append()
        self.assertEqual(b1["sequence"], 1)
        self.assertEqual(b1["prev_event_hash"], ledger.GENESIS)
        self.assertEqual(a2["prev_event_hash"], a1["hash"])

    def test_payload_hash_matches_payload(self):
        event = self.append(payload={"email": "x@example.com"})
        self.assertEqual(
            event["payload_hash"], canonical.canonical_hash({"email": "x@example.com"})
        )

    def test_bad_actor_rejected(self):
        with self.assertRaises(ledger.LedgerError):
            self.append(actor="robot")

    def test_malformed_ref_rejected(self):
        with self.assertRaises(ValueError):
            self.append(canonical_ref="Contact")

    def test_reopening_continues_the_chain(self):
        self.append()
        self.append()
        reopened = ledger.EventLog(self.path)
        third = reopened.append(TENANT, "system", "contact.upsert", {"email": "z@example.com"},
                                canonical_ref=REF, source_node_id=NODE_A)
        self.assertEqual(third["sequence"], 3)
        ok, problems = reopened.verify()
        self.assertTrue(ok, problems)


class TestVerify(LedgerCase):
    def test_clean_chain(self):
        for _ in range(5):
            self.append()
        ok, problems = ledger.EventLog(self.path).verify()
        self.assertTrue(ok, problems)
        self.assertEqual(problems, [])

    def test_payload_tamper_detected(self):
        self.append(payload={"email": "asha@example.com"})
        self.append()
        with open(self.path, encoding="utf-8") as f:
            lines = f.readlines()
        lines[0] = lines[0].replace("asha@example.com", "mallory@example.com")
        with open(self.path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        ok, problems = ledger.EventLog(self.path).verify()
        self.assertFalse(ok)
        self.assertTrue(any("altered" in p or "payload hash" in p for p in problems))

    def test_deleted_event_detected(self):
        for _ in range(3):
            self.append()
        with open(self.path, encoding="utf-8") as f:
            lines = f.readlines()
        with open(self.path, "w", encoding="utf-8") as f:
            f.writelines([lines[0], lines[2]])

        ok, problems = ledger.EventLog(self.path).verify()
        self.assertFalse(ok)
        self.assertTrue(any("sequence gap" in p or "broken link" in p for p in problems))

    def test_reordered_events_detected(self):
        self.append(payload={"email": "a@example.com"})
        self.append(payload={"email": "b@example.com"})
        with open(self.path, encoding="utf-8") as f:
            lines = f.readlines()
        with open(self.path, "w", encoding="utf-8") as f:
            f.writelines([lines[1], lines[0]])

        ok, problems = ledger.EventLog(self.path).verify()
        self.assertFalse(ok)

    def test_tenant_scoped_verify(self):
        self.append()
        self.append(tenant_id=OTHER)
        ok, problems = ledger.EventLog(self.path).verify(tenant_id=OTHER)
        self.assertTrue(ok, problems)


class TestQueries(LedgerCase):
    def test_knows_at_returns_last_value_before_horizon(self):
        self.append(payload={"email": "early@example.com"}, source_node_id=NODE_A,
                    timestamp="2026-11-01T09:00:00Z")
        self.append(payload={"email": "late@example.com"}, source_node_id=NODE_A,
                    timestamp="2026-11-01T15:00:00Z")
        self.append(payload={"email": "other@example.com"}, source_node_id=NODE_B,
                    timestamp="2026-11-01T10:00:00Z")

        at_noon = self.log.knows_at(TENANT, REF, "2026-11-01T12:00:00Z")
        self.assertEqual(at_noon[NODE_A]["email"], "early@example.com")
        self.assertEqual(at_noon[NODE_B]["email"], "other@example.com")

        at_evening = self.log.knows_at(TENANT, REF, "2026-11-01T18:00:00Z")
        self.assertEqual(at_evening[NODE_A]["email"], "late@example.com")

    def test_knows_at_ignores_other_references(self):
        self.append()
        self.append(canonical_ref="Contact:018f0000-0000-7000-8000-00000000c999")
        known = self.log.knows_at(TENANT, REF, "2030-01-01T00:00:00Z")
        self.assertEqual(len(known), 1)

    def test_history_is_ordered(self):
        for i in range(3):
            self.append(payload={"n": i})
        rows = self.log.history(TENANT, REF)
        self.assertEqual([r["payload"]["n"] for r in rows], [0, 1, 2])

    def test_history_empty_for_unknown_ref(self):
        self.assertEqual(self.log.history(TENANT, "Contact:nope"), [])


class TestAnchoring(LedgerCase):
    def test_anchor_reports_head_and_length(self):
        self.append()
        self.append()
        record = self.log.anchor()
        head = record["heads"][TENANT]
        self.assertEqual(head["length"], 2)
        self.assertEqual(len(head["head"]), 64)

    def test_write_anchor_appends_a_line(self):
        self.append()
        anchor_path = os.path.join(self.dir, "anchor.jsonl")
        self.log.write_anchor(anchor_path)
        self.log.write_anchor(anchor_path)
        with open(anchor_path, encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn("at", lines[0])
        self.assertEqual(lines[0]["heads"][TENANT]["length"], 1)


if __name__ == "__main__":
    unittest.main()
