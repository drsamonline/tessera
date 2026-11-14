import json
import os
import shutil
import tempfile
import unittest

from tessera import canonical, mcp, openapi
from tessera.api import Api, Principal, Request
from tessera.connectors import SimulatedConnector
from tessera.ledger import EventLog
from tessera.mesh import Mesh, Node
from tessera.projection import Projection
from tessera.workforce import Occupant, Seat, Workforce

TENANT = "018f0000-0000-7000-8000-000000000001"
CONTACT = "018f0000-0000-7000-8000-00000000c001"
KEY = b"test-key"


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
        self.dir = tempfile.mkdtemp(prefix="tessera-api-")
        self.log = EventLog(os.path.join(self.dir, "ledger.jsonl"))

        self.mesh = Mesh(TENANT, self.log)
        self.crm = SimulatedConnector("hubspot", "sales", page_size=10)
        self.support = SimulatedConnector("zendesk", "support", page_size=10)
        self.mesh.register(Node("hubspot", self.crm, "sales",
                                authority={"email": "authority"}, trust=0.8))
        self.mesh.register(Node("zendesk", self.support, "support", trust=0.6))
        self.crm.seed("Contact", contact())
        self.support.seed("Contact", contact(email="other@example.com"))
        self.mesh.sync("Contact")

        self.projection = Projection(self.log, TENANT).build()

        self.wf = Workforce(TENANT, KEY, log=self.log)
        self.wf.register_seat(Seat(id="s1", name="Triage", version=1,
                                   capability_manifest=["email"], escalation_ladder=["s2"]))
        self.wf.register_seat(Seat(id="s2", name="Specialist", version=1,
                                   capability_manifest=["email"]))
        self.wf.register_occupant(Occupant(id="o1", type="human", principal_id="p1",
                                           seat_id="s1", trust_score=0.9))

        self.tokens = {
            "reader": Principal("reader", ("read",)),
            "writer": Principal("writer", ("read", "write"), role="manager"),
            "worker": Principal("worker", ("read", "workforce")),
            "auditor": Principal("auditor", ("audit",)),
            "root": Principal("root", ("admin",)),
        }
        self.api = Api(TENANT, self.tokens, log=self.log, mesh=self.mesh,
                       projection=self.projection, workforce=self.wf)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def call(self, method, path, token=None, query=None, body=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.api.handle(Request(method=method, path=path, query=query or {},
                                       headers=headers, body=body))


class TestAuth(Case):
    def test_health_needs_no_token(self):
        response = self.call("GET", "/health")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["status"], "ok")

    def test_missing_token_is_401(self):
        self.assertEqual(self.call("GET", "/v1/objects/Contact").status, 401)

    def test_unknown_token_is_401(self):
        self.assertEqual(self.call("GET", "/v1/objects/Contact", token="nope").status, 401)

    def test_wrong_scope_is_403(self):
        response = self.call("POST", f"/v1/objects/Contact/{CONTACT}/fields/email",
                             token="reader", body={"value": "x@example.com"})
        self.assertEqual(response.status, 403)
        self.assertEqual(response.body["scope"], "write")

    def test_admin_scope_covers_everything(self):
        self.assertEqual(self.call("GET", "/v1/objects/Contact", token="root").status, 200)

    def test_unknown_route_is_404(self):
        self.assertEqual(self.call("GET", "/v1/nope", token="reader").status, 404)


class TestReads(Case):
    def test_list(self):
        response = self.call("GET", "/v1/objects/Contact", token="reader")
        self.assertEqual(response.status, 200)
        self.assertIn(CONTACT, response.body["ids"])

    def test_unknown_object_is_404(self):
        self.assertEqual(self.call("GET", "/v1/objects/Wombat", token="reader").status, 404)

    def test_get_record(self):
        response = self.call("GET", f"/v1/objects/Contact/{CONTACT}", token="reader")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["record"]["full_name"], "Asha Rao")

    def test_missing_record_is_404(self):
        other = "018f0000-0000-7000-8000-0000000000ff"
        self.assertEqual(self.call("GET", f"/v1/objects/Contact/{other}",
                                   token="reader").status, 404)

    def test_history(self):
        response = self.call("GET", f"/v1/objects/Contact/{CONTACT}/history", token="reader")
        self.assertEqual(response.status, 200)
        self.assertGreaterEqual(len(response.body["events"]), 1)
        self.assertIn("hash", response.body["events"][0])

    def test_as_of_requires_at(self):
        response = self.call("GET", f"/v1/objects/Contact/{CONTACT}/as-of", token="reader")
        self.assertEqual(response.status, 400)

    def test_as_of(self):
        # the projection is a raw replay: the last write wins, and the last write
        # synced was zendesk's. Merging is the mesh's job, not the projection's.
        response = self.call("GET", f"/v1/objects/Contact/{CONTACT}/as-of",
                             token="reader", query={"at": "2030-01-01T00:00:00Z"})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["record"]["email"], "other@example.com")

    def test_unified_view(self):
        response = self.call("GET", f"/v1/mesh/view/Contact/{CONTACT}", token="reader")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["fields"]["email"]["rule"], "authority_map")


class TestWrites(Case):
    def test_write_field(self):
        response = self.call("POST", f"/v1/objects/Contact/{CONTACT}/fields/email",
                             token="writer", body={"value": "new@example.com"})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["node"], "hubspot")
        self.assertEqual(response.body["principal"], "writer")

    def test_write_missing_value_is_400(self):
        response = self.call("POST", f"/v1/objects/Contact/{CONTACT}/fields/email",
                             token="writer", body={})
        self.assertEqual(response.status, 400)

    def test_a_mutation_writes_an_audit_event_naming_the_caller(self):
        before = sum(1 for _ in self.log.events(TENANT))
        self.call("POST", f"/v1/objects/Contact/{CONTACT}/fields/email",
                  token="writer", body={"value": "audited@example.com"})
        events = [e for e in self.log.events(TENANT) if e["action"] == "api.call"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["principal"], "writer")
        self.assertGreater(sum(1 for _ in self.log.events(TENANT)), before)

    def test_a_read_does_not_write_an_audit_event(self):
        self.call("GET", "/v1/objects/Contact", token="reader")
        self.assertEqual([e for e in self.log.events(TENANT) if e["action"] == "api.call"], [])


class TestWorkforceRoutes(Case):
    def test_assign(self):
        response = self.call("POST", "/v1/tasks", token="worker",
                             body={"seat_id": "s1", "required_capabilities": ["email"]})
        self.assertEqual(response.status, 201)
        self.assertEqual(response.body["occupant"], "o1")

    def test_assign_missing_seat_is_400(self):
        self.assertEqual(self.call("POST", "/v1/tasks", token="worker", body={}).status, 400)

    def test_assign_to_an_unknown_seat_is_409(self):
        response = self.call("POST", "/v1/tasks", token="worker", body={"seat_id": "nope"})
        self.assertEqual(response.status, 409)

    def test_escalate(self):
        assigned = self.call("POST", "/v1/tasks", token="worker",
                             body={"seat_id": "s1", "required_capabilities": ["email"]})
        task_id = assigned.body["task"]
        response = self.call("POST", f"/v1/tasks/{task_id}/escalate", token="worker",
                             body={"trigger": "low_confidence"})
        self.assertEqual(response.status, 201)
        self.assertEqual(response.body["to"], "s2")
        self.assertTrue(response.body["signature"])


class TestAuditRoute(Case):
    def test_verify(self):
        response = self.call("GET", "/v1/audit/verify", token="auditor")
        self.assertEqual(response.status, 200)
        self.assertTrue(response.body["chain_ok"])
        self.assertTrue(response.body["rebuildable"])


class TestOpenApi(unittest.TestCase):
    def setUp(self):
        self.doc = openapi.build_document()

    def test_version(self):
        self.assertEqual(self.doc["openapi"], "3.1.0")

    def test_structurally_valid(self):
        self.assertEqual(openapi.validate(self.doc), [])

    def test_validates_against_the_real_spec_when_available(self):
        try:
            import openapi_spec_validator  # noqa: F401
        except ImportError:
            self.skipTest("openapi-spec-validator is not installed; "
                          "the structural check above is what ran")
        self.assertEqual(openapi.validate_full(self.doc), [])

    def test_every_route_appears_in_the_document(self):
        served = {(method, pattern) for method, pattern in openapi.route_paths(_stub_api())}
        described = {(op["method"].upper(), op["pattern"]) for op in openapi.OPERATIONS}
        self.assertEqual(served, described, "the contract and the router must agree")

    def test_every_object_has_a_schema(self):
        schemas = self.doc["components"]["schemas"]
        for name in canonical.OBJECTS:
            self.assertIn(name, schemas)
            self.assertIn("properties", schemas[name])

    def test_required_fields_match_the_canonical_schema(self):
        schemas = self.doc["components"]["schemas"]
        expected = [f for f, (_k, req) in canonical.SCHEMA["Contact"].items() if req]
        self.assertEqual(sorted(schemas["Contact"]["required"]), sorted(expected))

    def test_every_operation_has_a_scope_or_is_documented_as_public(self):
        for path, item in self.doc["paths"].items():
            for method, op in item.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                if op["operationId"] == "health":
                    self.assertNotIn("security", op)
                else:
                    self.assertIn("security", op)
                    self.assertIn("x-required-scope", op)

    def test_the_document_is_json_serialisable(self):
        self.assertGreater(len(json.dumps(self.doc)), 1000)


class TestMcp(Case):
    def test_ten_tools(self):
        self.assertEqual(len(mcp.TOOLS), 10)

    def test_every_tool_carries_schema_scope_and_audit(self):
        self.assertEqual(mcp.validate_tools(), [])

    def test_discovery_document(self):
        doc = mcp.discovery_document()
        self.assertEqual(len(doc["tools"]), 10)
        for tool in doc["tools"]:
            self.assertIn("inputSchema", tool)
            self.assertIn("auth_scope", tool)
            self.assertIn("audit_action", tool)

    def test_unknown_tool(self):
        with self.assertRaises(mcp.McpError):
            mcp.dispatch(self.api, "nope", {}, self.tokens["root"])

    def test_scope_is_enforced(self):
        with self.assertRaises(mcp.McpError) as ctx:
            mcp.dispatch(self.api, "write_field", {"object": "Contact", "id": CONTACT,
                                                   "field": "email", "value": "x"},
                         self.tokens["reader"])
        self.assertIn("write", str(ctx.exception))

    def test_missing_argument_is_rejected(self):
        with self.assertRaises(mcp.McpError):
            mcp.dispatch(self.api, "get_record", {"object": "Contact"},
                         self.tokens["reader"])

    def test_a_read_tool_returns_data(self):
        result = mcp.dispatch(self.api, "get_record",
                              {"object": "Contact", "id": CONTACT}, self.tokens["reader"])
        self.assertEqual(result["record"]["full_name"], "Asha Rao")

    def test_every_dispatch_emits_an_audit_event(self):
        mcp.dispatch(self.api, "list_objects", {"object": "Contact"}, self.tokens["reader"])
        events = [e for e in self.log.events(TENANT) if e["action"] == "mcp.call"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["tool"], "list_objects")
        self.assertEqual(events[0]["payload"]["principal"], "reader")

    def test_a_failed_call_is_also_audited(self):
        with self.assertRaises(mcp.McpError):
            mcp.dispatch(self.api, "get_record",
                         {"object": "Contact", "id": "018f0000-0000-7000-8000-0000000000ff"},
                         self.tokens["reader"])
        events = [e for e in self.log.events(TENANT) if e["action"] == "mcp.call"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["status"], 404)

    def test_the_audit_event_hashes_the_arguments_not_the_values(self):
        mcp.dispatch(self.api, "get_record",
                     {"object": "Contact", "id": CONTACT}, self.tokens["reader"])
        event = [e for e in self.log.events(TENANT) if e["action"] == "mcp.call"][0]
        self.assertNotIn("id", json.dumps(event["payload"]))
        self.assertIn("arguments_hash", event["payload"])


def _stub_api():
    from tessera.api import Api as A
    return A("tenant", {})


if __name__ == "__main__":
    unittest.main()
