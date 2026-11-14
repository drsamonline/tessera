import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from tessera import canonical, compliance
from tessera.ledger import EventLog
from tessera.projection import Projection

TENANT = "018f0000-0000-7000-8000-000000000001"
CONTACT = "018f0000-0000-7000-8000-00000000c001"
KEY = b"audit-key"
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


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
        self.dir = tempfile.mkdtemp(prefix="tessera-comp-")
        self.log = EventLog(os.path.join(self.dir, "ledger.jsonl"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, record=None, at="2026-11-01T09:00:00Z"):
        return self.log.append(TENANT, "system", "contact.sync",
                               {"record": record or contact()},
                               canonical_ref=canonical.make_ref("Contact", CONTACT),
                               source_node_id="hubspot", timestamp=at)

    def projection(self):
        return Projection(self.log, TENANT).build()


class TestConsent(Case):
    def setUp(self):
        super().setUp()
        self.registry = compliance.ConsentRegistry(self.log, TENANT)

    def test_grant_then_permitted(self):
        self.registry.grant("subject-1", "marketing", "notice-2026-01")
        self.assertTrue(self.registry.is_permitted("subject-1", "marketing"))

    def test_consent_is_per_purpose(self):
        self.registry.grant("subject-1", "support", "notice-2026-01")
        self.assertTrue(self.registry.is_permitted("subject-1", "support"))
        self.assertFalse(self.registry.is_permitted("subject-1", "marketing"),
                         "a grant for one purpose is not a grant for another")

    def test_withdrawal_takes_effect(self):
        self.registry.grant("subject-1", "marketing", "notice-2026-01")
        self.registry.withdraw("subject-1", "marketing")
        self.assertFalse(self.registry.is_permitted("subject-1", "marketing"))

    def test_withdrawal_of_something_never_granted(self):
        with self.assertRaises(compliance.ComplianceError):
            self.registry.withdraw("subject-1", "marketing")

    def test_a_different_basis_does_not_rest_on_consent(self):
        self.assertTrue(self.registry.is_permitted("subject-1", "contract",
                                                   lawful_basis="contract"))

    def test_a_notice_version_is_required(self):
        with self.assertRaises(compliance.ComplianceError):
            self.registry.grant("subject-1", "marketing", "")

    def test_unknown_basis(self):
        with self.assertRaises(compliance.ComplianceError):
            self.registry.grant("subject-1", "marketing", "n1", lawful_basis="vibes")

    def test_grants_and_withdrawals_are_logged(self):
        self.registry.grant("subject-1", "marketing", "notice-2026-01")
        self.registry.withdraw("subject-1", "marketing")
        actions = [e["action"] for e in self.log.events(TENANT)]
        self.assertIn("consent.granted", actions)
        self.assertIn("consent.withdrawn", actions)


class TestDsar(Case):
    def setUp(self):
        super().setUp()
        self.write()
        self.service = compliance.DsarService(self.projection(), self.log, TENANT)

    def test_open_sets_a_due_date(self):
        request = self.service.open("asha@example.com", "access", now=NOW)
        self.assertEqual(request.due_at, NOW + timedelta(days=30))
        self.assertFalse(request.is_overdue(NOW))

    def test_overdue(self):
        request = self.service.open("asha@example.com", "access", now=NOW)
        self.assertTrue(request.is_overdue(NOW + timedelta(days=31)))
        self.assertEqual(self.service.overdue(NOW + timedelta(days=31)), [request])

    def test_completion_stops_the_clock(self):
        request = self.service.open("asha@example.com", "access", now=NOW)
        self.service.complete(request.id, now=NOW + timedelta(days=2))
        self.assertFalse(request.is_overdue(NOW + timedelta(days=40)))

    def test_unknown_request_type(self):
        with self.assertRaises(compliance.ComplianceError):
            self.service.open("asha@example.com", "delete-everything")

    def test_unknown_state(self):
        request = self.service.open("asha@example.com", "access", now=NOW)
        with self.assertRaises(compliance.ComplianceError):
            request.advance("shredded")

    def test_export_contains_the_record(self):
        bundle = self.service.export("asha@example.com")
        self.assertEqual(len(bundle["records"]), 1)
        self.assertEqual(bundle["records"][0]["record"]["full_name"], "Asha Rao")

    def test_export_contains_the_ledger_events(self):
        bundle = self.service.export("asha@example.com")
        self.assertGreaterEqual(len(bundle["ledger_events"]), 1)
        self.assertIn("hash", bundle["ledger_events"][0])

    def test_export_is_hashable_and_stable_in_shape(self):
        bundle = self.service.export("asha@example.com")
        self.assertIn("bundle_hash", bundle)
        self.assertEqual(len(bundle["bundle_hash"]), 64)

    def test_export_of_an_unknown_subject_is_empty_but_complete(self):
        bundle = self.service.export("nobody@example.com")
        self.assertEqual(bundle["records"], [])
        self.assertTrue(bundle["complete"])

    def test_the_clock_is_configurable(self):
        service = compliance.DsarService(self.projection(), self.log, TENANT, due_days=7)
        request = service.open("asha@example.com", "access", now=NOW)
        self.assertEqual(request.due_at, NOW + timedelta(days=7))

    def test_requests_are_logged(self):
        request = self.service.open("asha@example.com", "access", now=NOW)
        self.service.complete(request.id, now=NOW)
        actions = [e["action"] for e in self.log.events(TENANT)]
        self.assertIn("dsar.received", actions)
        self.assertIn("dsar.completed", actions)


class TestRetention(Case):
    def setUp(self):
        super().setUp()
        self.write()
        self.policy = compliance.RetentionPolicy(self.log, TENANT)

    def test_due_after_the_window(self):
        # the record was written on 2026-11-01, so at NOW it is already 13 days old
        self.policy.set_rule("Contact", days=30)
        self.assertEqual(self.policy.due(self.projection(), NOW), [])
        later = NOW + timedelta(days=20)
        self.assertEqual(len(self.policy.due(self.projection(), later)), 1)

    def test_legal_hold_wins(self):
        self.policy.set_rule("Contact", days=1, legal_hold=True)
        later = NOW + timedelta(days=365)
        self.assertEqual(self.policy.due(self.projection(), later), [],
                         "a legal hold outranks expiry")

    def test_sweep_logs_and_the_projection_drops_the_record(self):
        self.policy.set_rule("Contact", days=1)
        later = NOW + timedelta(days=10)
        result = self.policy.sweep(self.projection(), later)
        self.assertEqual(result["expired"], 1)
        rebuilt = self.projection()
        self.assertEqual(rebuilt.get("Contact", CONTACT), None,
                         "an expired record leaves the projection on rebuild")

    def test_unknown_object(self):
        with self.assertRaises(compliance.ComplianceError):
            self.policy.set_rule("Wombat", days=10)

    def test_negative_window(self):
        with self.assertRaises(compliance.ComplianceError):
            self.policy.set_rule("Contact", days=-1)


class TestErasure(Case):
    def setUp(self):
        super().setUp()
        self.write()
        self.service = compliance.DsarService(self.projection(), self.log, TENANT)

    def test_erase_tombstones_and_the_projection_drops_it(self):
        result = compliance.erase(self.projection(), self.log, TENANT,
                                  "asha@example.com")
        self.assertEqual(result["erased"], 1)
        rebuilt = self.projection()
        self.assertIsNone(rebuilt.get("Contact", CONTACT))

    def test_the_tombstone_is_in_the_ledger(self):
        compliance.erase(self.projection(), self.log, TENANT, "asha@example.com")
        actions = [e["action"] for e in self.log.events(TENANT)]
        self.assertIn("record.erased", actions)

    def test_the_chain_still_verifies_after_an_erasure(self):
        compliance.erase(self.projection(), self.log, TENANT, "asha@example.com")
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)

    def test_the_export_no_longer_contains_the_record(self):
        compliance.erase(self.projection(), self.log, TENANT, "asha@example.com")
        bundle = self.service.export("asha@example.com")
        self.assertEqual(bundle["records"], [])

    def test_the_result_says_it_is_a_tombstone_not_a_destruction(self):
        result = compliance.erase(self.projection(), self.log, TENANT,
                                  "asha@example.com")
        self.assertIn("tombstoned", result["note"])


class TestAuditExport(Case):
    def setUp(self):
        super().setUp()
        self.write()
        self.write(contact(email="later@example.com"), at="2026-11-05T09:00:00Z")
        self.export = compliance.AuditExport(self.log, TENANT, KEY)

    def test_build_and_verify(self):
        bundle = self.export.build("2026-11-01T00:00:00Z", "2026-11-30T00:00:00Z")
        self.assertEqual(bundle["count"], 2)
        self.assertTrue(self.export.verify(bundle))

    def test_a_tampered_bundle_fails(self):
        bundle = self.export.build("2026-11-01T00:00:00Z", "2026-11-30T00:00:00Z")
        bundle["count"] = 99
        self.assertFalse(self.export.verify(bundle))

    def test_a_different_key_fails(self):
        bundle = self.export.build("2026-11-01T00:00:00Z", "2026-11-30T00:00:00Z")
        other = compliance.AuditExport(self.log, TENANT, b"another-key")
        self.assertFalse(other.verify(bundle))

    def test_a_narrow_window(self):
        bundle = self.export.build("2026-11-04T00:00:00Z", "2026-11-06T00:00:00Z")
        self.assertEqual(bundle["count"], 1)

    def test_no_key_is_refused(self):
        with self.assertRaises(compliance.ComplianceError):
            compliance.AuditExport(self.log, TENANT, b"")


if __name__ == "__main__":
    unittest.main()
