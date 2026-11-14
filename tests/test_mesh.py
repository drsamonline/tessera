import os
import tempfile
import unittest

from tessera import canonical
from tessera.connectors import NativeConnector, SimulatedConnector
from tessera.ledger import EventLog
from tessera.mesh import Mesh, Node

TENANT = "018f0000-0000-7000-8000-000000000001"
CONTACT = "018f0000-0000-7000-8000-00000000c001"
ACT_1 = "018f0000-0000-7000-8000-0000000ac001"
ACT_2 = "018f0000-0000-7000-8000-0000000ac002"


def contact(record_id=CONTACT, **over):
    payload = {
        "id": record_id,
        "tenant_id": TENANT,
        "valid_from": "2026-11-01T09:00:00Z",
        "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted",
        "lawful_basis": "consent",
        "purpose_id": "sales-outreach",
        "retention_policy_id": "rp-24m",
        "full_name": "Asha Rao",
        "email": "asha@example.com",
    }
    payload.update(over)
    return payload


def activity(record_id, node_subject, kind="email"):
    return {
        "id": record_id,
        "tenant_id": TENANT,
        "valid_from": "2026-11-01T10:00:00Z",
        "tx_time": "2026-11-01T10:00:01Z",
        "consent_state": "granted",
        "lawful_basis": "consent",
        "purpose_id": "sales-outreach",
        "retention_policy_id": "rp-24m",
        "kind": kind,
        "occurred_at": "2026-11-01T09:30:00Z",
        "subject_ref": node_subject,
        "body": "logged",
    }


class MeshCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-mesh-")
        self.log = EventLog(os.path.join(self.dir, "ledger.jsonl"))
        self.mesh = Mesh(TENANT, self.log)

        self.crm = SimulatedConnector("hubspot", "sales", page_size=2)
        self.support = SimulatedConnector("zendesk", "support", page_size=2)
        self.native = NativeConnector(page_size=2)

    def tearDown(self):
        for name in os.listdir(self.dir):
            os.unlink(os.path.join(self.dir, name))
        os.rmdir(self.dir)

    def register_default(self):
        self.mesh.register(Node("hubspot", self.crm, "sales",
                                authority={"email": "authority"}, trust=0.8))
        self.mesh.register(Node("zendesk", self.support, "support", trust=0.6))


class TestRegistration(MeshCase):
    def test_register_and_list(self):
        self.register_default()
        self.assertEqual(sorted(self.mesh.nodes), ["hubspot", "zendesk"])

    def test_duplicate_registration_rejected(self):
        self.register_default()
        with self.assertRaises(ValueError):
            self.mesh.register(Node("hubspot", self.crm, "sales"))

    def test_nodes_for_an_object(self):
        self.register_default()
        self.assertEqual([n.id for n in self.mesh.nodes_for("Contact")],
                         ["hubspot", "zendesk"])
        self.assertEqual(self.mesh.nodes_for("Invoice"), [])


class TestSync(MeshCase):
    def test_sync_stores_and_logs(self):
        self.register_default()
        self.crm.seed("Contact", contact(email="from-hubspot@example.com"))
        self.support.seed("Contact", contact(email="from-zendesk@example.com"))

        result = self.mesh.sync("Contact")
        self.assertEqual(result["stored"], {"hubspot": 1, "zendesk": 1})
        self.assertEqual(self.mesh.record_ids("Contact"), [CONTACT])

        events = list(self.log.events(TENANT))
        self.assertEqual(len(events), 2, "one ledger event per stored record")
        self.assertEqual({e["source_node_id"] for e in events}, {"hubspot", "zendesk"})
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)

    def test_invalid_record_is_rejected_not_stored(self):
        self.register_default()
        broken = contact()
        del broken["full_name"]
        self.crm.seed("Contact", contact())  # seed validates, so bypass for this one
        self.crm._records["Contact"][CONTACT] = broken

        result = self.mesh.sync("Contact")
        self.assertEqual(result["rejected"].get("hubspot"), 1)
        self.assertEqual(self.mesh.record_ids("Contact"), [])

    def test_sync_tolerates_a_failing_node(self):
        self.register_default()
        self.support.seed("Contact", contact())
        self.crm.fail_times = 5
        result = self.mesh.sync("Contact")
        self.assertEqual(result["stored"]["hubspot"], 0)
        self.assertEqual(result["stored"]["zendesk"], 1)


class TestUnifiedView(MeshCase):
    def setUp(self):
        super().setUp()
        self.register_default()
        self.crm.seed("Contact", contact(email="hubspot@example.com"))
        self.support.seed("Contact", contact(email="zendesk@example.com"))
        self.mesh.sync("Contact")

    def test_one_record_across_two_nodes(self):
        view = self.mesh.unified_view("Contact", CONTACT)
        self.assertEqual(view["nodes"], ["hubspot", "zendesk"])
        self.assertEqual(view["object"], "Contact")

    def test_authority_wins_the_field(self):
        view = self.mesh.unified_view("Contact", CONTACT)
        self.assertEqual(view["fields"]["email"]["source"], "hubspot")
        self.assertEqual(view["fields"]["email"]["rule"], "authority_map")
        self.assertEqual(view["fields"]["email"]["value"], "hubspot@example.com")

    def test_identical_values_are_not_a_conflict(self):
        view = self.mesh.unified_view("Contact", CONTACT)
        self.assertEqual(view["fields"]["full_name"]["value"], "Asha Rao")
        self.assertEqual(view["fields"]["full_name"]["rule"], "agreement")
        self.assertNotIn("full_name", [c["field"] for c in view["conflicts"]],
                         "agreeing nodes are not a conflict")
        self.assertEqual([c["field"] for c in view["conflicts"]], ["email"],
                         "only the field that actually disagrees is reported")

    def test_unknown_record_raises(self):
        with self.assertRaises(KeyError):
            self.mesh.unified_view("Contact", "nope")

    def test_conflicts_are_reported_with_both_values(self):
        view = self.mesh.unified_view("Contact", CONTACT)
        email = [c for c in view["conflicts"] if c["field"] == "email"]
        self.assertEqual(len(email), 1)
        self.assertEqual(email[0]["rule"], "authority_map")
        self.assertEqual(set(email[0]["values"].values()),
                         {"hubspot@example.com", "zendesk@example.com"})


class TestWrite(MeshCase):
    def test_write_goes_to_the_authority(self):
        self.register_default()
        self.crm.seed("Contact", contact())
        self.support.seed("Contact", contact())
        self.mesh.sync("Contact")

        result = self.mesh.write_field("Contact", CONTACT, "email", "new@example.com")
        self.assertEqual(result["node"], "hubspot")

        view = self.mesh.unified_view("Contact", CONTACT)
        self.assertEqual(view["fields"]["email"]["value"], "new@example.com")

        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)

    def test_bidirectional_field_writes_to_the_most_trusted_node(self):
        self.register_default()
        self.crm.seed("Contact", contact())
        self.support.seed("Contact", contact())
        self.mesh.sync("Contact")
        # nobody declares ownership of full_name, so both are bidirectional
        result = self.mesh.write_field("Contact", CONTACT, "full_name", "Someone Else")
        self.assertEqual(result["node"], "hubspot", "trust 0.8 beats trust 0.6")
        self.assertEqual(result["mode"], "bidirectional")

    def test_a_field_mirrored_everywhere_is_refused(self):
        self.mesh.register(Node("hubspot", self.crm, "sales",
                                authority={"email": "mirror"}, trust=0.8))
        self.mesh.register(Node("zendesk", self.support, "support",
                                authority={"email": "mirror"}, trust=0.6))
        self.crm.seed("Contact", contact())
        self.support.seed("Contact", contact())
        self.mesh.sync("Contact")
        with self.assertRaises(PermissionError):
            self.mesh.write_field("Contact", CONTACT, "email", "x@example.com")

    def test_a_mirror_node_is_skipped_in_favour_of_a_writable_one(self):
        self.mesh.register(Node("hubspot", self.crm, "sales",
                                authority={"email": "mirror"}, trust=0.9))
        self.mesh.register(Node("zendesk", self.support, "support", trust=0.3))
        self.crm.seed("Contact", contact())
        self.support.seed("Contact", contact())
        self.mesh.sync("Contact")
        result = self.mesh.write_field("Contact", CONTACT, "email", "y@example.com")
        self.assertEqual(result["node"], "zendesk",
                         "the trusted node is a mirror, so the writable one takes it")

    def test_field_modes_reports_every_node(self):
        self.register_default()
        self.crm.seed("Contact", contact())
        self.support.seed("Contact", contact())
        self.mesh.sync("Contact")
        modes = self.mesh.field_modes("Contact", CONTACT, "email")
        self.assertEqual(modes, {"hubspot": "authority", "zendesk": "bidirectional"})

    def test_write_that_breaks_the_schema_is_refused(self):
        self.register_default()
        self.crm.seed("Contact", contact())
        self.mesh.sync("Contact")
        with self.assertRaises(ValueError):
            self.mesh.write_field("Contact", CONTACT, "email", 42)


class TestActivation(MeshCase):
    def test_not_reached_with_one_node(self):
        self.mesh.register(Node("hubspot", self.crm, "sales"))
        self.crm.seed("Contact", contact())
        self.mesh.sync("Contact")
        self.assertFalse(self.mesh.activation()["reached"])

    def test_not_reached_with_one_category(self):
        self.mesh.register(Node("a", self.crm, "sales"))
        self.mesh.register(Node("b", self.support, "sales"))
        self.crm.seed("Contact", contact())
        self.support.seed("Contact", contact())
        self.mesh.sync("Contact")
        self.assertFalse(self.mesh.activation()["reached"])

    def test_reached_with_two_categories_and_activity_from_both(self):
        self.register_default()
        ref = canonical.make_ref("Contact", CONTACT)
        self.crm.seed("Contact", contact())
        self.support.seed("Contact", contact())
        self.crm.seed("Activity", activity(ACT_1, ref, kind="email"))
        self.support.seed("Activity", activity(ACT_2, ref, kind="ticket"))

        self.mesh.sync("Contact")
        self.mesh.sync("Activity")

        result = self.mesh.activation()
        self.assertTrue(result["reached"], result)
        self.assertEqual(result["contact"], CONTACT)
        self.assertEqual(result["categories"], ["sales", "support"])
        self.assertEqual(result["activity_sources"], ["hubspot", "zendesk"])

    def test_activity_from_one_node_is_not_enough(self):
        self.register_default()
        ref = canonical.make_ref("Contact", CONTACT)
        self.crm.seed("Contact", contact())
        self.support.seed("Contact", contact())
        self.crm.seed("Activity", activity(ACT_1, ref))
        self.mesh.sync("Contact")
        self.mesh.sync("Activity")
        self.assertFalse(self.mesh.activation()["reached"])


if __name__ == "__main__":
    unittest.main()
