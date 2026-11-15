"""Tenant isolation: one process, several customers, no shared anything.

Isolation by construction — a separate mesh, a separate ledger file and a separate
projection per tenant — is cheaper to audit than a `tenant_id` column and the
discipline to always filter on it.
"""
import unittest

from tessera import api
from tessera.tenants import multi_tenant_api

T1 = "018f0000-0000-7000-8000-000000000001"
T2 = "018f0000-0000-7000-8000-000000000002"


def build(tenant, tenant_tokens):
    token = tenant_tokens[0] if tenant_tokens else "unused"
    return api.demo_api(tenant_id=tenant, token=token, standalone=True)


class TestTenantIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.router = multi_tenant_api([T1, T2], {
            "token-one": (T1, api.Principal("p1", ("admin",), role="admin")),
            "token-two": (T2, api.Principal("p2", ("admin",), role="admin")),
        }, build)

    def call(self, token, path, method="GET", body=None):
        return self.router.handle(api.Request(
            method=method, path=path, query={},
            headers={"Authorization": f"Bearer {token}"}, body=body))

    def contacts(self, token):
        return self.call(token, "/v1/objects/Contact").body["ids"]

    def test_each_token_sees_only_its_own_tenant(self):
        one, two = self.contacts("token-one"), self.contacts("token-two")
        self.assertTrue(one and two)
        self.assertEqual(set(one) & set(two), set(),
                         "two tenants must not share a record id")

    def test_an_unknown_token_is_refused(self):
        self.assertEqual(self.call("not-a-token", "/v1/objects/Contact").status, 401)

    def test_no_token_is_refused(self):
        response = self.router.handle(api.Request(
            method="GET", path="/v1/objects/Contact", query={}, headers={}, body=None))
        self.assertEqual(response.status, 401)

    def test_a_create_lands_in_one_tenant_only(self):
        before_one = len(self.contacts("token-one"))
        before_two = len(self.contacts("token-two"))
        created = self.call("token-one", "/v1/objects/Contact", "POST", {
            "full_name": "Only In One", "consent_state": "granted",
            "lawful_basis": "consent", "purpose_id": "sales"})
        self.assertEqual(created.status, 201)
        self.assertEqual(len(self.contacts("token-one")), before_one + 1)
        self.assertEqual(len(self.contacts("token-two")), before_two,
                         "a create in one tenant must not appear in another")

    def test_one_tenant_cannot_read_anothers_record(self):
        created = self.call("token-one", "/v1/objects/Contact", "POST", {
            "full_name": "Private Person", "consent_state": "granted",
            "lawful_basis": "consent", "purpose_id": "sales"})
        record_id = created.body["id"]
        self.assertEqual(self.call("token-one", f"/v1/objects/Contact/{record_id}").status, 200)
        self.assertEqual(self.call("token-two", f"/v1/objects/Contact/{record_id}").status, 404,
                         "the other tenant must not be able to read it by id")

    def test_each_tenant_has_its_own_ledger(self):
        one = self.router.apis[T1].log
        two = self.router.apis[T2].log
        self.assertIsNot(one, two)
        self.assertNotEqual(getattr(one, "path", id(one)), getattr(two, "path", id(two)))

    def test_health_names_the_tenants(self):
        health = self.router.health()
        self.assertEqual(sorted(health["tenants"]), sorted([T1, T2]))
        self.assertEqual(health["tokens"], 2)

    def test_a_token_bound_to_a_missing_tenant_is_a_configuration_error(self):
        router = multi_tenant_api([T1], {"t": (T1, api.Principal("p", ("admin",)))}, build)
        router.bindings["orphan"] = "tenant-that-does-not-exist"
        response = router.handle(api.Request(
            method="GET", path="/v1/objects/Contact", query={},
            headers={"Authorization": "Bearer orphan"}, body=None))
        self.assertEqual(response.status, 503)
        self.assertEqual(response.body["error"], "tenant_not_running")


if __name__ == "__main__":
    unittest.main()
