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


class TestTombstone(unittest.TestCase):
    """Deletion in an append-only chain: the projection forgets, the ledger does not."""

    def setUp(self):
        self.api = api.demo_api(standalone=True)
        self.headers = {"Authorization": "Bearer demo-token"}

    def call(self, method, path, body=None):
        return self.api.handle(api.Request(method=method, path=path, query={},
                                           headers=self.headers, body=body))

    def a_contact(self):
        return self.call("GET", "/v1/objects/Contact").body["ids"][0]

    def test_a_reason_is_required(self):
        contact = self.a_contact()
        for body in ({}, {"reason": ""}, {"reason": "   "}):
            response = self.call("DELETE", f"/v1/objects/Contact/{contact}", body)
            self.assertEqual(response.status, 400, body)
            self.assertEqual(response.body["error"], "reason_required")

    def test_a_tombstoned_record_leaves_the_list(self):
        contact = self.a_contact()
        before = len(self.call("GET", "/v1/objects/Contact").body["ids"])
        self.call("DELETE", f"/v1/objects/Contact/{contact}",
                  {"reason": "duplicate of an existing contact"})
        after = self.call("GET", "/v1/objects/Contact").body["ids"]
        self.assertEqual(len(after), before - 1)
        self.assertNotIn(contact, after)

    def test_a_tombstoned_record_is_gone_from_a_read(self):
        contact = self.a_contact()
        self.call("DELETE", f"/v1/objects/Contact/{contact}", {"reason": "duplicate"})
        self.assertEqual(self.call("GET", f"/v1/objects/Contact/{contact}").status, 404)

    def test_the_ledger_keeps_the_record_and_the_reason(self):
        contact = self.a_contact()
        self.call("DELETE", f"/v1/objects/Contact/{contact}",
                  {"reason": "duplicate of an existing contact"})
        events = [event for event in self.api.log.events()
                  if event["action"] == "record.tombstoned"]
        self.assertTrue(events, "the tombstone is an event, not an absence")
        self.assertEqual(events[-1]["payload"]["reason"], "duplicate of an existing contact")
        self.assertTrue(events[-1]["payload"]["tombstone"])

    def test_deleting_twice_is_a_conflict_not_a_second_tombstone(self):
        contact = self.a_contact()
        self.call("DELETE", f"/v1/objects/Contact/{contact}", {"reason": "duplicate"})
        second = self.call("DELETE", f"/v1/objects/Contact/{contact}", {"reason": "again"})
        self.assertEqual(second.status, 409)
        tombstones = [event for event in self.api.log.events()
                      if event["action"] == "record.tombstoned"]
        self.assertEqual(len(tombstones), 1)

    def test_an_unknown_record_is_404(self):
        response = self.call("DELETE",
                             "/v1/objects/Contact/018f0000-0000-7000-8000-0000000000ff",
                             {"reason": "never existed"})
        self.assertEqual(response.status, 404)


class TestRepeatedCreates(unittest.TestCase):
    """A create must be visible on the very next read, every time.

    It was not. `record.created` carried no `canonical_ref`, so the projection
    skipped it; the record appeared only when a later `sync` happened to carry it.
    The first two creates worked and the third silently did not, which is the worst
    shape a bug can take: it looks like a slow read.
    """

    def test_five_creates_in_a_row_are_all_visible(self):
        api_ = api.demo_api(standalone=True)
        headers = {"Authorization": "Bearer demo-token"}

        def call(method, path, body=None):
            return api_.handle(api.Request(method=method, path=path, query={},
                                           headers=headers, body=body))

        start = len(call("GET", "/v1/objects/Contact").body["ids"])
        for index in range(5):
            created = call("POST", "/v1/objects/Contact", {
                "full_name": f"Person {index}", "email": f"person{index}@example.com",
                "consent_state": "pending", "lawful_basis": "legitimate_interest",
                "purpose_id": "support"})
            self.assertEqual(created.status, 201)
            after = call("GET", "/v1/objects/Contact").body["ids"]
            self.assertIn(created.body["id"], after,
                          f"create {index} is not visible to the next read")
            self.assertEqual(len(after), start + index + 1)

    def test_a_create_is_in_the_ledger_with_a_reference(self):
        api_ = api.demo_api(standalone=True)
        headers = {"Authorization": "Bearer demo-token"}
        created = api_.handle(api.Request(
            method="POST", path="/v1/objects/Contact", query={}, headers=headers,
            body={"full_name": "Referenced", "email": "referenced@example.com",
                  "consent_state": "pending", "lawful_basis": "legitimate_interest",
                  "purpose_id": "support"}))
        events = [e for e in api_.log.events() if e["action"] == "record.created"]
        mine = [e for e in events if e["payload"].get("id") == created.body["id"]]
        self.assertTrue(mine, "the create is not in the ledger")
        self.assertEqual(mine[0]["canonical_ref"],
                         f"Contact:{created.body['id']}")
