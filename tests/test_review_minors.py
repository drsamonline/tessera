"""The five findings the review left open. Each one is a behaviour, not a style."""
import os
import tempfile
import unittest

from tessera import api, canonical, conflict, ledger, mesh, openapi
from tessera.connector import TransientError
from tessera.connectors import NativeConnector
from tessera.projection import Projection

TENANT = "018f0000-0000-7000-8000-000000000001"


class TestO03ConnectorFailureIs502(unittest.TestCase):
    def test_a_failing_connector_is_a_bad_gateway(self):
        log = ledger.EventLog(os.path.join(tempfile.mkdtemp(), "l.jsonl"))
        federated = mesh.Mesh(TENANT, log)
        node = NativeConnector(node_id="n1")
        node.seed("Contact", {
            "id": "018f0000-0000-7000-8000-00000000c001", "tenant_id": TENANT,
            "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
            "consent_state": "granted", "lawful_basis": "consent", "purpose_id": "p",
            "retention_policy_id": "r", "full_name": "Asha", "email": "a@example.com",
        })
        federated.register(mesh.Node("n1", node, "sales", authority={"email": "authority"}))
        federated.sync("Contact")

        def explode(*_args, **_kwargs):
            raise TransientError("upstream is down")

        node.write = explode
        service = api.Api(TENANT, {"t": api.Principal("t", ("read", "write"), role="manager")},
                          log=log, mesh=federated,
                          projection=Projection(log, TENANT).build())
        response = service.handle(api.Request(
            method="POST", path="/v1/objects/Contact/018f0000-0000-7000-8000-00000000c001"
                                "/fields/email",
            query={}, headers={"Authorization": "Bearer t"}, body={"value": "b@example.com"}))
        self.assertEqual(response.status, 502)
        self.assertEqual(response.body["error"], "connector_failure")


class TestO04UuidShape(unittest.TestCase):
    def _payload(self, value):
        return {"id": value, "tenant_id": canonical.uuid7(),
                "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
                "consent_state": "granted", "lawful_basis": "consent", "purpose_id": "p",
                "retention_policy_id": "r", "full_name": "Asha"}

    def test_thirty_six_dashes_is_not_a_uuid(self):
        problems = canonical.validate("Contact", self._payload("-" * 36))
        self.assertTrue(any("expected uuid" in p for p in problems))

    def test_a_real_uuid_passes(self):
        self.assertEqual(canonical.validate("Contact", self._payload(canonical.uuid7())), [])

    def test_a_uuid_with_a_bad_group_is_refused(self):
        problems = canonical.validate(
            "Contact", self._payload("018f0000-0000-7000-8000-00000000c00Z"))
        self.assertTrue(any("expected uuid" in p for p in problems))


class TestO08FieldPriorityIsDeterministic(unittest.TestCase):
    def test_the_same_set_in_a_different_order_resolves_the_same_way(self):
        def candidates(order):
            return [conflict.Conflict(node, f"v-{node}", "2026-11-01T09:00:00Z", 0.5)
                    for node in order]

        forward = conflict.resolve("email", candidates(["b", "a", "c"]),
                                   {}, field_priority=["email"])
        backward = conflict.resolve("email", candidates(["c", "a", "b"]),
                                    {}, field_priority=["email"])
        self.assertEqual(forward["winner"], backward["winner"])
        self.assertEqual(forward["winner"], "a", "the tiebreak is the lowest node id")


class TestO09AuthRateLimit(unittest.TestCase):
    def test_ten_wrong_tokens_then_429(self):
        service = api.Api(TENANT, {"t": api.Principal("t", ("read",))}, log=None)
        request = api.Request(method="GET", path="/v1/objects/Contact", query={},
                              headers={"Authorization": "Bearer nope"}, body=None)
        for _ in range(service.AUTH_FAILURE_LIMIT):
            self.assertEqual(service.handle(request).status, 401)
        self.assertEqual(service.handle(request).status, 429)

    def test_a_correct_token_is_unaffected(self):
        service = api.Api(TENANT, {"t": api.Principal("t", ("read",))}, log=None)
        good = api.Request(method="GET", path="/v1/objects/Contact", query={},
                           headers={"Authorization": "Bearer t"}, body=None)
        self.assertNotEqual(service.handle(good).status, 429)


class TestO10PathParameters(unittest.TestCase):
    def test_a_placeholder_without_a_parameter_is_reported(self):
        document = openapi.build_document(api.Api(TENANT, {}))
        broken = {**document, "paths": {"/v1/objects/{object}": {"get": {
            "operationId": "x", "summary": "x", "responses": {"200": {"description": "ok"}},
            "security": [{"bearerAuth": []}]}}}}
        problems = openapi.validate(broken)
        self.assertTrue(any("{object} has no path parameter" in p for p in problems))

    def test_the_real_document_is_clean(self):
        self.assertEqual(openapi.validate(openapi.build_document(api.Api(TENANT, {}))), [])


if __name__ == "__main__":
    unittest.main()
