import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from tessera import canonical, checkpoint, ledger, projection
from tessera.api import Api, Principal, Request
from tessera.ratelimit import NodeBudget

TENANT = "018f0000-0000-7000-8000-000000000001"
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


class TestR08TimestampPrecision(unittest.TestCase):
    """R-08: two precisions of ISO timestamp compared as strings sort wrongly."""

    def test_parse_time_handles_both_precisions(self):
        seconds = canonical.parse_time("2026-11-14T05:20:44Z")
        millis = canonical.parse_time("2026-11-14T05:20:44.582Z")
        self.assertLess(seconds, millis, "the string compare said the opposite")

    def test_parse_time_handles_an_offset(self):
        self.assertEqual(canonical.parse_time("2026-11-14T10:50:44+05:30"),
                         canonical.parse_time("2026-11-14T05:20:44Z"))

    def test_parse_time_rejects_a_non_string(self):
        with self.assertRaises(ValueError):
            canonical.parse_time(1234)

    def test_knows_at_is_correct_across_precisions(self):
        d = tempfile.mkdtemp()
        try:
            log = ledger.EventLog(os.path.join(d, "l.jsonl"))
            log.append(TENANT, "system", "x", {"v": "early"}, canonical_ref=REF,
                       timestamp="2026-11-14T05:20:44Z")          # seconds
            log.append(TENANT, "system", "x", {"v": "late"}, canonical_ref=REF,
                       timestamp="2026-11-14T05:20:44.582Z")      # milliseconds
            known = log.knows_at(TENANT, REF, "2026-11-14T05:20:44.100Z")
            self.assertEqual(known["native"]["v"], "early",
                             "a millisecond-precision event must not win at an earlier instant")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_as_of_is_correct_across_precisions(self):
        d = tempfile.mkdtemp()
        try:
            log = ledger.EventLog(os.path.join(d, "l.jsonl"))
            log.append(TENANT, "system", "c", {"record": contact()}, canonical_ref=REF,
                       timestamp="2026-11-14T05:20:44Z")
            log.append(TENANT, "system", "c", {"record": contact(email="new@example.com")},
                       canonical_ref=REF, timestamp="2026-11-14T05:20:44.582Z")
            proj = projection.Projection(log, TENANT).build()
            early = proj.as_of("Contact", contact()["id"], "2026-11-14T05:20:44.100Z")
            self.assertEqual(early["email"], "asha@example.com")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestR09RevertRemovesRecords(unittest.TestCase):
    """R-09: reverting to a checkpoint could not remove a record created after it."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-r09-")
        self.log = ledger.EventLog(os.path.join(self.dir, "l.jsonl"))
        self.cp = checkpoint.Checkpointer(self.log, TENANT,
                                          os.path.join(self.dir, "cp.jsonl"), every=1)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_record_created_after_the_checkpoint_is_removed_on_revert(self):
        self.log.append(TENANT, "system", "c", {"record": contact()}, canonical_ref=REF)
        self.cp.write()
        self.log.append(TENANT, "system", "c", {"record": contact(email="new@example.com")},
                        canonical_ref=REF)
        result = self.cp.revert_to(0)
        self.assertEqual(result["restored"], 1)
        rebuilt = projection.Projection(self.log, TENANT).build()
        self.assertEqual(rebuilt.get("Contact", contact()["id"])["email"],
                         "asha@example.com")

    def test_a_record_that_did_not_exist_at_the_checkpoint_disappears(self):
        self.log.append(TENANT, "system", "other", {"record": contact()},
                        canonical_ref="Contact:018f0000-0000-7000-8000-00000000c002")
        self.cp.write()
        new_ref = "Contact:018f0000-0000-7000-8000-00000000c003"
        self.log.append(TENANT, "system", "c", {"record": contact()}, canonical_ref=new_ref)
        self.cp.revert_to(0)
        rebuilt = projection.Projection(self.log, TENANT).build()
        self.assertIsNone(rebuilt.get("Contact", "018f0000-0000-7000-8000-00000000c003"),
                          "a record created after the checkpoint must be reverted away")

    def test_the_chain_still_verifies(self):
        self.log.append(TENANT, "system", "c", {"record": contact()}, canonical_ref=REF)
        self.cp.write()
        self.log.append(TENANT, "system", "c", {"record": contact()}, canonical_ref=REF)
        self.cp.revert_to(0)
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)


class TestR10NoInertLimit(unittest.TestCase):
    def test_queue_fields_are_gone(self):
        budget = NodeBudget("n")
        self.assertFalse(hasattr(budget, "max_queue"))
        self.assertNotIn("queued", budget.snapshot())


class TestR11AuditActor(unittest.TestCase):
    """R-11: every API caller was recorded as a human, including agents."""

    def test_an_agent_is_recorded_as_an_agent(self):
        d = tempfile.mkdtemp()
        try:
            log = ledger.EventLog(os.path.join(d, "l.jsonl"))
            tokens = {"a1": Principal("agent-7", ("admin",), role="admin", kind="agent")}
            api = Api(TENANT, tokens, log=log, projection=projection.Projection(log, TENANT))
            api.handle(Request("POST", "/v1/tasks", headers={"Authorization": "Bearer a1"},
                               body={"seat_id": "s1"}))
            events = [e for e in log.events(TENANT) if e["action"] == "api.call"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["actor"], "agent")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_a_human_is_recorded_as_a_human(self):
        d = tempfile.mkdtemp()
        try:
            log = ledger.EventLog(os.path.join(d, "l.jsonl"))
            tokens = {"h1": Principal("priya", ("admin",), role="admin")}
            api = Api(TENANT, tokens, log=log, projection=projection.Projection(log, TENANT))
            api.handle(Request("POST", "/v1/tasks", headers={"Authorization": "Bearer h1"},
                               body={"seat_id": "s1"}))
            event = [e for e in log.events(TENANT) if e["action"] == "api.call"][0]
            self.assertEqual(event["actor"], "human")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestR12Durability(unittest.TestCase):
    def test_fsync_is_called_when_durable(self):
        d = tempfile.mkdtemp()
        calls = []
        real_fsync = os.fsync
        os.fsync = lambda fd: calls.append(fd)
        try:
            log = ledger.EventLog(os.path.join(d, "l.jsonl"), durable=True)
            log.append(TENANT, "system", "x", {"v": 1})
            self.assertEqual(len(calls), 1)
        finally:
            os.fsync = real_fsync
            shutil.rmtree(d, ignore_errors=True)

    def test_fsync_is_not_called_by_default(self):
        d = tempfile.mkdtemp()
        calls = []
        real_fsync = os.fsync
        os.fsync = lambda fd: calls.append(fd)
        try:
            log = ledger.EventLog(os.path.join(d, "l.jsonl"))
            log.append(TENANT, "system", "x", {"v": 1})
            self.assertEqual(calls, [])
        finally:
            os.fsync = real_fsync
            shutil.rmtree(d, ignore_errors=True)


class TestR13ConstantTimeToken(unittest.TestCase):
    def test_a_token_is_matched_exactly(self):
        tokens = {"good": Principal("p", ("read",))}
        api = Api(TENANT, tokens)
        self.assertIsNotNone(api._principal_for("good"))
        self.assertIsNone(api._principal_for("goo"))
        self.assertIsNone(api._principal_for("good "))
        self.assertIsNone(api._principal_for(""))


if __name__ == "__main__":
    unittest.main()
