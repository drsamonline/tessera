"""Standalone mode: TESSERA as the CRM, with nothing behind it.

The product claim is that it federates when there are systems to federate and
works alone when there are none. This file tests the second half.
"""
import unittest

from tessera import api


class TestStandalone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = api.demo_api(standalone=True)
        cls.headers = {"Authorization": "Bearer demo-token"}

    def call(self, method, path, body=None):
        return self.api.handle(api.Request(method=method, path=path, query={},
                                           headers=self.headers, body=body))

    def test_it_serves_contacts_with_no_external_system(self):
        response = self.call("GET", "/v1/objects/Contact")
        self.assertEqual(response.status, 200)
        self.assertGreaterEqual(len(response.body["ids"]), 3)

    def test_the_native_store_is_the_source(self):
        listing = self.call("GET", "/v1/objects/Contact")
        first = listing.body["ids"][0]
        view = self.call("GET", f"/v1/mesh/view/Contact/{first}")
        sources = {field["source"] for field in view.body["fields"].values()}
        self.assertEqual(sources, {"native"})

    def test_a_record_can_be_created(self):
        before = len(self.call("GET", "/v1/objects/Contact").body["ids"])
        created = self.call("POST", "/v1/objects/Contact", {
            "full_name": "Created Here", "email": "created@example.com",
            "consent_state": "pending", "lawful_basis": "legitimate_interest",
            "purpose_id": "support"})
        self.assertEqual(created.status, 201, created.body)
        self.assertEqual(created.body["node"], "native")
        after = len(self.call("GET", "/v1/objects/Contact").body["ids"])
        self.assertEqual(after, before + 1, "the create must be visible to the next read")

    def test_a_created_record_can_be_read_back(self):
        created = self.call("POST", "/v1/objects/Contact", {
            "full_name": "Readable Person", "email": "readable@example.com",
            "consent_state": "granted", "lawful_basis": "consent", "purpose_id": "sales"})
        record = self.call("GET", f"/v1/objects/Contact/{created.body['id']}")
        self.assertEqual(record.status, 200)
        self.assertEqual(record.body["record"]["full_name"], "Readable Person")

    def test_a_created_record_can_be_edited(self):
        created = self.call("POST", "/v1/objects/Contact", {
            "full_name": "Editable Person", "email": "editable@example.com",
            "phone": "+91 90000 11111", "consent_state": "granted",
            "lawful_basis": "consent", "purpose_id": "sales"})
        edited = self.call("POST", f"/v1/objects/Contact/{created.body['id']}/fields/phone",
                           {"value": "+91 90000 22222"})
        self.assertEqual(edited.status, 200, edited.body)
        record = self.call("GET", f"/v1/objects/Contact/{created.body['id']}")
        self.assertEqual(record.body["record"]["phone"], "+91 90000 22222")

    def test_consent_and_lawful_basis_are_not_defaulted(self):
        """A record with an invented lawful basis is a compliance claim nobody made."""
        response = self.call("POST", "/v1/objects/Contact", {"full_name": "No Basis"})
        self.assertEqual(response.status, 422)
        self.assertIn("lawful_basis", response.body["detail"])

    def test_the_create_is_in_the_ledger(self):
        created = self.call("POST", "/v1/objects/Contact", {
            "full_name": "Ledgered Person", "consent_state": "granted",
            "lawful_basis": "consent", "purpose_id": "sales"})
        events = list(self.api.log.events())
        self.assertTrue(any(event["action"] == "record.created" and
                            event["payload"]["id"] == created.body["id"]
                            for event in events))


if __name__ == "__main__":
    unittest.main()


class TestDemoReferences(unittest.TestCase):
    """A dangling reference renders as a company nobody has, which looks like a bug in the screen."""

    @classmethod
    def setUpClass(cls):
        cls.api = api.demo_api()
        cls.headers = {"Authorization": "Bearer demo-token"}

    def ids(self, object_name):
        response = self.api.handle(api.Request(
            method="GET", path=f"/v1/objects/{object_name}", query={},
            headers=self.headers, body=None))
        return response.body.get("ids", [])

    def record(self, object_name, record_id):
        response = self.api.handle(api.Request(
            method="GET", path=f"/v1/objects/{object_name}/{record_id}", query={},
            headers=self.headers, body=None))
        return response.body["record"]

    def test_every_deal_points_at_a_company_that_exists(self):
        company_refs = {f"Company:{cid}" for cid in self.ids("Company")}
        self.assertTrue(company_refs)
        for deal_id in self.ids("Deal"):
            deal = self.record("Deal", deal_id)
            self.assertIn(deal["company_ref"], company_refs,
                          f"deal {deal['name']} points at a company that is not there")

    def test_every_contact_points_at_a_company_that_exists(self):
        company_refs = {f"Company:{cid}" for cid in self.ids("Company")}
        for contact_id in self.ids("Contact"):
            contact = self.record("Contact", contact_id)
            self.assertIn(contact["company_ref"], company_refs)

    def test_a_contact_and_its_deals_share_a_company(self):
        contacts = self.ids("Contact")
        deals = self.ids("Deal")
        contact = self.record("Contact", contacts[0])
        deal = self.record("Deal", deals[0])
        self.assertEqual(contact["company_ref"], deal["company_ref"],
                         "the demo's first contact and first deal should be the same account")
