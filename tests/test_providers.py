import unittest

from tessera import canonical, conformance
from tessera.connector import AuthError, ContractError, RateLimited, SchemaDrift, TransientError
from tessera.providers import HubSpotConnector, SalesforceConnector, ZendeskConnector
from tessera.transport import RecordedTransport, Response

TENANT = "018f0000-0000-7000-8000-000000000001"


# ---------------------------------------------------------------------------
# Fakes that speak each provider's documented shapes
# ---------------------------------------------------------------------------

class FakeHubSpot:
    """CRM v3: results/paging.next.after, POST returns the object."""

    def __init__(self, page_size=2):
        self.rows: dict[str, dict] = {}
        self.page_size = page_size
        self.next_id = 1

    def __call__(self, method, url, params, body):
        if method == "GET" and url.endswith("/crm/v3/objects/contacts"):
            limit = int(params.get("limit", self.page_size))
            keys = sorted(self.rows, key=lambda k: int(k))
            start = int(params.get("after", 0) or 0)
            page = keys[start:start + limit]
            out = {"results": [self.rows[k] for k in page]}
            if start + limit < len(keys):
                out["paging"] = {"next": {"after": str(start + limit)}}
            return Response(200, out)
        if method == "POST":
            new_id = str(self.next_id)
            self.next_id += 1
            self.rows[new_id] = {"id": new_id, "properties": dict(body["properties"]),
                                 "updatedAt": "2026-11-01T09:00:00Z"}
            return Response(201, self.rows[new_id])
        if method == "PATCH":
            external = url.rsplit("/", 1)[-1]
            self.rows[external]["properties"].update(body.get("properties", {}))
            return Response(200, self.rows[external])
        return Response(404, {"message": "not found"})


class FakeSalesforce:
    """REST v60: records/done/nextRecordsUrl, POST returns {id, success}."""

    def __init__(self, page_size=2):
        self.rows: list[dict] = []
        self.page_size = page_size
        self.next_id = 1
        self.rest_offset = 0

    def _page(self, offset, next_url):
        page = self.rows[offset:offset + self.page_size]
        end = offset + self.page_size
        more = end < len(self.rows)
        body = {"totalSize": len(self.rows), "done": not more, "records": page}
        if more:
            self.rest_offset = end
            body["nextRecordsUrl"] = next_url
        return Response(200, body)

    def __call__(self, method, url, params, body):
        if method == "GET" and "/services/data/v60.0/query/" in url:
            return self._page(self.rest_offset, "/services/data/v60.0/query/01g-next")
        if method == "GET" and url.endswith("/services/data/v60.0/query"):
            return self._page(0, "/services/data/v60.0/query/01g-next")
        if method == "GET" and url.endswith("/services/data/v60.0/limits"):
            return Response(200, {"DailyApiRequests": {"Max": 1000}})
        if method == "POST" and "/sobjects/" in url:
            new_id = f"003{self.next_id:06d}"
            self.next_id += 1
            row = {"attributes": {"type": "Contact"}, "Id": new_id,
                   "LastModifiedDate": "2026-11-01T09:00:00.000+0000"}
            row.update(body)
            self.rows.append(row)
            return Response(201, {"id": new_id, "success": True})
        if method == "PATCH":
            return Response(204, None)
        return Response(404, [{"errorCode": "NOT_FOUND"}])


class FakeZendesk:
    """Support v2: users/meta.after_cursor, POST returns {user: {...}}."""

    def __init__(self, page_size=2):
        self.rows: list[dict] = []
        self.page_size = page_size
        self.next_id = 1

    def __call__(self, method, url, params, body):
        if method == "GET" and url.endswith("/api/v2/users/me"):
            return Response(200, {"user": {"id": 0, "name": "probe"}})
        if method == "GET" and url.endswith("/api/v2/users"):
            size = int(params.get("page[size]", self.page_size))
            start = int(params.get("page[after]", 0) or 0)
            page = self.rows[start:start + size]
            meta = {"has_more": start + size < len(self.rows)}
            if meta["has_more"]:
                meta["after_cursor"] = str(start + size)
            return Response(200, {"users": page, "meta": meta})
        if method == "POST" and url.endswith("/api/v2/users"):
            new_id = self.next_id
            self.next_id += 1
            row = {"id": new_id, "updated_at": "2026-11-01T09:00:00Z"}
            row.update(body)
            self.rows.append(row)
            return Response(201, {"user": row})
        if method == "PUT":
            return Response(200, {"user": {"id": 1}})
        return Response(404, {"error": "RecordNotFound"})


def hubspot(page_size=2):
    fake = FakeHubSpot(page_size)
    transport = RecordedTransport(fake)
    node = HubSpotConnector("hubspot", transport, TENANT, token="t", page_size=page_size)
    return node, transport, fake


def salesforce(page_size=2):
    fake = FakeSalesforce(page_size)
    transport = RecordedTransport(fake)
    node = SalesforceConnector("salesforce", transport, TENANT, token="t", page_size=page_size)
    return node, transport, fake


def zendesk(page_size=2):
    fake = FakeZendesk(page_size)
    transport = RecordedTransport(fake)
    node = ZendeskConnector("zendesk", transport, TENANT, token="t", page_size=page_size)
    return node, transport, fake


# ---------------------------------------------------------------------------
# The criterion: four connectors, one suite
# ---------------------------------------------------------------------------

class TestConformance(unittest.TestCase):
    def test_hubspot_conforms(self):
        node, _, _ = hubspot()
        report = conformance.run_conformance(node)
        self.assertTrue(report.ok, report.summary())

    def test_salesforce_conforms(self):
        node, _, _ = salesforce()
        report = conformance.run_conformance(node)
        self.assertTrue(report.ok, report.summary())

    def test_zendesk_conforms(self):
        node, _, _ = zendesk()
        report = conformance.run_conformance(node)
        self.assertTrue(report.ok, report.summary())

    def test_all_three_use_the_same_suite(self):
        reports = [conformance.run_conformance(build()) for build in
                   (lambda: hubspot()[0], lambda: salesforce()[0], lambda: zendesk()[0])]
        names = [{c.name for c in r.checks} for r in reports]
        self.assertEqual(names[0], names[1])
        self.assertEqual(names[1], names[2])
        self.assertTrue(all(r.ok for r in reports))


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------

class TestFieldMapping(unittest.TestCase):
    def test_hubspot_splits_and_rejoins_the_name(self):
        node, transport, _ = hubspot()
        payload = {
            "id": "018f0000-0000-7000-8000-00000000c001", "tenant_id": TENANT,
            "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
            "consent_state": "granted", "lawful_basis": "consent", "purpose_id": "p",
            "retention_policy_id": "r", "full_name": "Asha Rao", "email": "asha@example.com",
        }
        node.write("Contact", payload, "k1")
        sent = [c for c in transport.calls if c["method"] == "POST"][0]["body"]
        self.assertEqual(sent["properties"]["firstname"], "Asha")
        self.assertEqual(sent["properties"]["lastname"], "Rao")
        self.assertEqual(sent["properties"]["email"], "asha@example.com")

        page = node.read("Contact")
        self.assertEqual(page.records[0]["full_name"], "Asha Rao")

    def test_salesforce_uses_sobject_names(self):
        node, transport, _ = salesforce()
        payload = {
            "id": "018f0000-0000-7000-8000-00000000c002", "tenant_id": TENANT,
            "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
            "consent_state": "granted", "lawful_basis": "consent", "purpose_id": "p",
            "retention_policy_id": "r", "full_name": "Ravi Kumar", "email": "ravi@example.com",
        }
        node.write("Contact", payload, "k1")
        sent = [c for c in transport.calls if c["method"] == "POST"][0]["body"]
        self.assertEqual(sent["Name"], "Ravi Kumar")
        self.assertEqual(sent["Email"], "ravi@example.com")

    def test_zendesk_maps_name(self):
        node, transport, _ = zendesk()
        payload = {
            "id": "018f0000-0000-7000-8000-00000000c003", "tenant_id": TENANT,
            "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
            "consent_state": "granted", "lawful_basis": "consent", "purpose_id": "p",
            "retention_policy_id": "r", "full_name": "Meera Iyer", "email": "meera@example.com",
        }
        node.write("Contact", payload, "k1")
        sent = [c for c in transport.calls if c["method"] == "POST"][0]["body"]
        self.assertEqual(sent["name"], "Meera Iyer")


# ---------------------------------------------------------------------------
# Identity and the envelope
# ---------------------------------------------------------------------------

class TestIdentity(unittest.TestCase):
    def test_canonical_id_is_stable_across_reads(self):
        node, _, _ = hubspot()
        first = node.canonical_id("42")
        second = node.canonical_id("42")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 36)

    def test_the_same_external_id_in_two_nodes_is_two_records(self):
        a, _, _ = hubspot()
        b, _, _ = zendesk()
        self.assertNotEqual(a.canonical_id("42"), b.canonical_id("42"),
                            "an external id is only unique inside its own node")

    def test_written_record_keeps_the_canonical_id(self):
        node, _, _ = hubspot()
        payload = {
            "id": "018f0000-0000-7000-8000-00000000c004", "tenant_id": TENANT,
            "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
            "consent_state": "granted", "lawful_basis": "consent", "purpose_id": "p",
            "retention_policy_id": "r", "full_name": "Asha Rao",
        }
        node.write("Contact", payload, "k1")
        page = node.read("Contact")
        self.assertEqual(page.records[0]["id"], payload["id"])

    def test_envelope_carries_tenant_policy(self):
        node, _, _ = hubspot()
        node.policy["consent_state"] = "granted"
        node.policy["purpose_id"] = "support-resolution"
        node.transport.handler = FakeHubSpot()
        node.transport.handler.rows["1"] = {
            "id": "1", "properties": {"email": "a@example.com", "firstname": "A",
                                      "lastname": "B"},
            "updatedAt": "2026-11-01T09:00:00Z",
        }
        record = node.read("Contact").records[0]
        self.assertEqual(record["tenant_id"], TENANT)
        self.assertEqual(record["consent_state"], "granted")
        self.assertEqual(record["purpose_id"], "support-resolution")
        self.assertEqual(record["valid_from"], "2026-11-01T09:00:00Z")


# ---------------------------------------------------------------------------
# Pagination follows each provider's own cursor
# ---------------------------------------------------------------------------

class TestPagination(unittest.TestCase):
    def test_hubspot_uses_after(self):
        node, transport, fake = hubspot(page_size=2)
        for i in range(1, 6):
            fake.rows[str(i)] = {"id": str(i), "properties": {"email": f"{i}@x.com",
                                                              "firstname": "A",
                                                              "lastname": "B"},
                                 "updatedAt": "2026-11-01T09:00:00Z"}
        cursor, pages = None, 0
        while True:
            page = node.read("Contact", cursor)
            pages += 1
            cursor = page.cursor
            if cursor is None:
                break
        self.assertEqual(pages, 3)
        self.assertEqual(transport.calls[-1]["params"].get("after"), "4")

    def test_salesforce_follows_next_records_url(self):
        node, transport, fake = salesforce(page_size=2)
        for i in range(5):
            fake.rows.append({"attributes": {"type": "Contact"}, "Id": f"003{i}",
                              "Name": f"Person {i}", "LastModifiedDate": "2026-11-01T09:00:00Z"})
        records, cursor, pages = [], None, 0
        while True:
            page = node.read("Contact", cursor)
            pages += 1
            records.extend(page.records)
            cursor = page.cursor
            if cursor is None:
                break
        self.assertEqual(pages, 3)
        self.assertEqual(len(records), 5)
        self.assertTrue(any("/query/01g-next" in c["url"] for c in transport.calls))

    def test_zendesk_uses_after_cursor(self):
        node, transport, fake = zendesk(page_size=2)
        for i in range(5):
            fake.rows.append({"id": i, "name": f"Person {i}", "email": f"{i}@x.com",
                              "updated_at": "2026-11-01T09:00:00Z"})
        cursor, pages = None, 0
        while True:
            page = node.read("Contact", cursor)
            pages += 1
            cursor = page.cursor
            if cursor is None:
                break
        self.assertEqual(pages, 3)
        self.assertEqual(transport.calls[-1]["params"].get("page[after]"), "4")


# ---------------------------------------------------------------------------
# The taxonomy, applied at the transport
# ---------------------------------------------------------------------------

class TestErrorMapping(unittest.TestCase):
    def _node_raising(self, status, headers=None):
        transport = RecordedTransport(lambda *a: Response(status, {"error": "x"}, headers or {}))
        return HubSpotConnector("hubspot", transport, TENANT, token="t")

    def test_401_is_auth_error(self):
        with self.assertRaises(AuthError):
            self._node_raising(401).read("Contact")

    def test_403_is_auth_error(self):
        with self.assertRaises(AuthError):
            self._node_raising(403).read("Contact")

    def test_429_carries_retry_after(self):
        node = self._node_raising(429, {"Retry-After": "7"})
        with self.assertRaises(RateLimited) as ctx:
            node.read("Contact")
        self.assertEqual(ctx.exception.retry_after, 7.0)

    def test_500_is_transient(self):
        with self.assertRaises(TransientError):
            self._node_raising(500).read("Contact")

    def test_400_is_a_contract_error(self):
        with self.assertRaises(ContractError):
            self._node_raising(400).read("Contact")

    def test_unknown_object_is_schema_drift_before_any_request(self):
        node, transport, _ = hubspot()
        with self.assertRaises(SchemaDrift):
            node.read("Wombat")
        self.assertEqual(transport.calls, [], "the guard must run before the network")

    def test_health_reports_offline_when_the_transport_fails(self):
        node = self._node_raising(500)
        self.assertEqual(node.health().status, "offline")


if __name__ == "__main__":
    unittest.main()
