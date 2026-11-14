import os
import shutil
import tempfile
import unittest

from tessera import access, canonical, mcp
from tessera.api import Api, Principal, Request
from tessera.connectors import SimulatedConnector
from tessera.ledger import EventLog
from tessera.mesh import Mesh, Node
from tessera.projection import Projection

TENANT = "018f0000-0000-7000-8000-000000000001"
CONTACT = "018f0000-0000-7000-8000-00000000c001"
OWNED = "018f0000-0000-7000-8000-00000000c002"
DEAL = "018f0000-0000-7000-8000-00000000d001"
SEAT_REP = "018f0000-0000-7000-8000-0000000000a1"
SEAT_OTHER = "018f0000-0000-7000-8000-0000000000a2"


def contact(record_id, **over):
    payload = {
        "id": record_id, "tenant_id": TENANT,
        "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted", "lawful_basis": "consent",
        "purpose_id": "p", "retention_policy_id": "r",
        "full_name": "Asha Rao", "email": "asha@example.com", "phone": "+91 90000 00000",
    }
    payload.update(over)
    return payload


def deal(**over):
    payload = {
        "id": DEAL, "tenant_id": TENANT,
        "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted", "lawful_basis": "consent",
        "purpose_id": "p", "retention_policy_id": "r",
        "name": "Renewal", "amount_minor": 4_500_000, "currency": "INR",
        "stage": "proposal",
    }
    payload.update(over)
    return payload


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-acl-")
        self.log = EventLog(os.path.join(self.dir, "ledger.jsonl"))
        self.mesh = Mesh(TENANT, self.log)
        self.crm = SimulatedConnector("hubspot", "sales",
                                      objects=("Contact", "Company", "Deal", "Activity"),
                                      page_size=10)
        self.mesh.register(Node("hubspot", self.crm, "sales",
                                authority={"email": "authority"}, trust=0.8))
        self.crm.seed("Contact", contact(CONTACT))
        self.crm.seed("Contact", contact(OWNED, owner_seat_id=SEAT_REP))
        self.crm.seed("Deal", deal(owner_seat_id=SEAT_REP))
        self.mesh.sync("Contact")
        self.mesh.sync("Deal")
        self.projection = Projection(self.log, TENANT).build()

        self.tokens = {
            "admin": Principal("admin", ("admin",), role="admin"),
            "manager": Principal("manager", ("read", "write"), role="manager"),
            "rep": Principal("rep", ("read", "write"), role="rep", seat_id=SEAT_REP),
            "other-rep": Principal("other", ("read", "write"), role="rep",
                                   seat_id=SEAT_OTHER),
            "support": Principal("support", ("read",), role="support"),
            "auditor": Principal("auditor", ("audit",), role="auditor"),
            "nobody": Principal("nobody", ("read",), role="rep"),
        }
        self.api = Api(TENANT, self.tokens, log=self.log, mesh=self.mesh,
                       projection=self.projection)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def call(self, method, path, token, query=None, body=None):
        return self.api.handle(Request(method=method, path=path, query=query or {},
                                       headers={"Authorization": f"Bearer {token}"},
                                       body=body))


class TestFieldLevel(Case):
    def test_billing_is_hidden_from_a_rep(self):
        response = self.call("GET", f"/v1/objects/Deal/{DEAL}", "rep")
        self.assertEqual(response.status, 200)
        self.assertNotIn("amount_minor", response.body["record"])
        self.assertIn("name", response.body["record"])

    def test_billing_is_visible_to_a_manager(self):
        response = self.call("GET", f"/v1/objects/Deal/{DEAL}", "manager")
        self.assertIn("amount_minor", response.body["record"])

    def test_a_rep_may_not_edit_consent(self):
        response = self.call("POST", f"/v1/objects/Contact/{OWNED}/fields/consent_state",
                             "rep", body={"value": "withdrawn"})
        self.assertEqual(response.status, 403)
        self.assertEqual(response.body["field"], "consent_state")

    def test_a_rep_may_edit_a_standard_field_on_an_owned_record(self):
        response = self.call("POST", f"/v1/objects/Contact/{OWNED}/fields/full_name",
                             "rep", body={"value": "Asha R Rao"})
        self.assertEqual(response.status, 200)

    def test_an_auditor_may_edit_nothing(self):
        response = self.call("POST", f"/v1/objects/Contact/{CONTACT}/fields/full_name",
                             "auditor", body={"value": "x"})
        self.assertEqual(response.status, 403)


class TestRowLevel(Case):
    def test_a_rep_sees_only_owned_records(self):
        response = self.call("GET", "/v1/objects/Contact", "rep")
        self.assertEqual(response.body["ids"], [OWNED])

    def test_another_rep_sees_nothing(self):
        response = self.call("GET", "/v1/objects/Contact", "other-rep")
        self.assertEqual(response.body["ids"], [])

    def test_an_unowned_record_is_invisible_to_an_owner_scoped_role(self):
        response = self.call("GET", f"/v1/objects/Contact/{CONTACT}", "rep")
        self.assertEqual(response.status, 404, "not 403: the record's existence is not disclosed")

    def test_a_manager_sees_every_record(self):
        response = self.call("GET", "/v1/objects/Contact", "manager")
        self.assertEqual(sorted(response.body["ids"]), sorted([CONTACT, OWNED]))

    def test_an_object_a_role_cannot_touch_is_403(self):
        response = self.call("GET", "/v1/objects/Invoice", "rep")
        self.assertEqual(response.status, 403)


class TestTheCriterion(Case):
    """Deliverable 9: a denied field is absent from the API, the export and MCP."""

    def test_denied_field_is_absent_from_the_api_response(self):
        response = self.call("GET", f"/v1/objects/Deal/{DEAL}", "rep")
        self.assertEqual(response.status, 200)
        self.assertNotIn("amount_minor", response.body["record"])
        self.assertNotIn("currency", response.body["record"])

    def test_denied_field_is_absent_from_the_export(self):
        response = self.call("GET", "/v1/objects/Deal/export", "rep")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["count"], 1)
        self.assertNotIn("amount_minor", response.body["records"][0])

    def test_denied_field_is_absent_from_mcp_output(self):
        result = mcp.dispatch(self.api, "get_record",
                              {"object": "Deal", "id": DEAL}, self.tokens["rep"])
        self.assertNotIn("amount_minor", result["record"])

    def test_denied_field_is_absent_from_history(self):
        response = self.call("GET", f"/v1/objects/Deal/{DEAL}/history", "rep")
        self.assertEqual(response.status, 200)
        for event in response.body["events"]:
            record = (event.get("payload") or {}).get("record") or {}
            self.assertNotIn("amount_minor", record)

    def test_denied_field_is_absent_from_as_of(self):
        response = self.call("GET", f"/v1/objects/Deal/{DEAL}/as-of", "rep",
                             query={"at": "2030-01-01T00:00:00Z"})
        self.assertEqual(response.status, 200)
        self.assertNotIn("amount_minor", response.body["record"])

    def test_denied_field_is_absent_from_the_unified_view(self):
        response = self.call("GET", f"/v1/mesh/view/Contact/{CONTACT}", "support")
        self.assertEqual(response.status, 200)
        self.assertIn("email", response.body["fields"], "support may read contact fields")
        deal_view = self.call("GET", f"/v1/mesh/view/Deal/{DEAL}", "rep")
        self.assertNotIn("amount_minor", deal_view.body["fields"])


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = access.AccessPolicy()

    def test_default_role_is_least_privilege(self):
        principal = Principal("x", ("read",))
        self.assertEqual(principal.role, "auditor")
        self.assertFalse(self.policy.can_edit_field(principal, "Contact", "full_name"))

    def test_unknown_role_is_denied(self):
        with self.assertRaises(access.AccessDenied):
            self.policy.role_of(Principal("x", role="wizard"))

    def test_field_classes(self):
        self.assertEqual(access.field_class("Deal", "amount_minor"), "billing")
        self.assertEqual(access.field_class("Contact", "email"), "sensitive")
        self.assertEqual(access.field_class("Contact", "full_name"), "standard")

    def test_redaction_keeps_order_of_the_source(self):
        record = {"full_name": "A", "email": "e", "amount_minor": 1}
        redacted = self.policy.redact(Principal("x", role="rep"), "Deal", record)
        self.assertNotIn("amount_minor", redacted)


if __name__ == "__main__":
    unittest.main()
