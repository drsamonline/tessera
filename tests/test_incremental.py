import os
import shutil
import tempfile
import unittest

from tessera import canonical, ledger, projection

TENANT = "018f0000-0000-7000-8000-000000000001"
OTHER = "018f0000-0000-7000-8000-000000000002"
REF = "Contact:018f0000-0000-7000-8000-00000000c001"


def contact(**over):
    payload = {
        "id": "018f0000-0000-7000-8000-00000000c001", "tenant_id": TENANT,
        "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted", "lawful_basis": "consent",
        "purpose_id": "p", "retention_policy_id": "r",
        "full_name": "Asha Rao", "email": "asha@example.com",
    }
    payload.update(over)
    return payload


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-inc-")
        self.log = ledger.EventLog(os.path.join(self.dir, "ledger.jsonl"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, **over):
        return self.log.append(TENANT, "system", "contact.sync",
                               {"record": contact(**over)}, canonical_ref=REF,
                               source_node_id="hubspot")


class TestReadFrom(Case):
    def test_reads_everything_from_zero(self):
        for i in range(3):
            self.write(email=f"{i}@example.com")
        events, offset = self.log.read_from(0, TENANT)
        self.assertEqual(len(events), 3)
        self.assertGreater(offset, 0)

    def test_reads_only_what_arrived(self):
        self.write(email="a@example.com")
        events, offset = self.log.read_from(0, TENANT)
        self.assertEqual(len(events), 1)
        self.write(email="b@example.com")
        more, offset2 = self.log.read_from(offset, TENANT)
        self.assertEqual(len(more), 1)
        self.assertEqual(more[0]["payload"]["record"]["email"], "b@example.com")
        self.assertGreater(offset2, offset)

    def test_nothing_new_returns_nothing(self):
        self.write()
        _, offset = self.log.read_from(0, TENANT)
        more, offset2 = self.log.read_from(offset, TENANT)
        self.assertEqual(more, [])
        self.assertEqual(offset2, offset)

    def test_the_tenant_filter_applies(self):
        self.write()
        self.log.append(OTHER, "system", "x", {"record": contact()}, canonical_ref=REF)
        events, _ = self.log.read_from(0, TENANT)
        self.assertEqual(len(events), 1)

    def test_size_grows(self):
        start = self.log.size()
        self.write()
        self.assertGreater(self.log.size(), start)


class TestIncrementalProjection(Case):
    def test_refresh_applies_only_new_events(self):
        self.write(email="a@example.com")
        self.write(email="b@example.com")
        live = projection.Projection(self.log, TENANT, incremental=True)
        self.assertEqual(live.refresh(), 2)
        self.write(email="c@example.com")
        self.assertEqual(live.refresh(), 1, "only the new event was applied")
        self.assertEqual(live.get("Contact", contact()["id"])["email"], "c@example.com")

    def test_incremental_and_full_agree(self):
        for i in range(20):
            self.write(email=f"{i}@example.com")
        live = projection.Projection(self.log, TENANT, incremental=True)
        live.refresh()
        full = projection.Projection(self.log, TENANT).build()
        self.assertEqual(live.fingerprint(), full.fingerprint())
        self.assertEqual(live.count(), full.count())

    def test_refresh_with_no_new_events_is_a_no_op(self):
        self.write()
        live = projection.Projection(self.log, TENANT, incremental=True)
        live.refresh()
        fingerprint = live.fingerprint()
        self.assertEqual(live.refresh(), 0)
        self.assertEqual(live.fingerprint(), fingerprint)

    def test_a_rebuild_still_matches_an_incremental_projection(self):
        self.write(email="a@example.com")
        live = projection.Projection(self.log, TENANT, incremental=True)
        live.refresh()
        self.write(email="b@example.com")
        live.refresh()
        result = live.verify_rebuildable()
        self.assertTrue(result["rebuildable"], result)


class TestAnchoredVerify(Case):
    def setUp(self):
        super().setUp()
        for i in range(5):
            self.write(email=f"{i}@example.com")

    def anchor_at(self, sequence):
        events = list(self.log.events(TENANT))
        event = [e for e in events if e["sequence"] == sequence][0]
        return {"sequence": event["sequence"], "hash": event["hash"]}

    def test_a_clean_log_verifies_from_an_anchor(self):
        ok, problems = self.log.verify(anchor=self.anchor_at(3))
        self.assertTrue(ok, problems)

    def test_tampering_after_the_anchor_is_caught(self):
        anchor = self.anchor_at(2)
        path = self.log.path
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        lines[3] = lines[3].replace("3@example.com", "evil@example.com")
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        ok, problems = self.log.verify(anchor=anchor)
        self.assertFalse(ok)

    def test_tampering_before_the_anchor_is_not_caught_and_that_is_the_trade(self):
        anchor = self.anchor_at(4)
        path = self.log.path
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        lines[0] = lines[0].replace("0@example.com", "evil@example.com")
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        ok, problems = self.log.verify(anchor=anchor)
        self.assertTrue(ok, "an anchored check cannot see behind its own anchor")
        full_ok, _ = self.log.verify()
        self.assertFalse(full_ok, "a full verify still catches it")

    def test_a_full_verify_catches_everything(self):
        ok, _ = self.log.verify()
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
