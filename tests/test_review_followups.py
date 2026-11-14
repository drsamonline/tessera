import json
import os
import shutil
import tempfile
import unittest

from tessera import conformance, sync
from tessera.connectors import SimulatedConnector
from tessera.ledger import EventLog
from tessera.projection import Projection
from tessera.providers import HubSpotConnector
from tessera.transport import RecordedTransport, Response

TENANT = "018f0000-0000-7000-8000-000000000001"
REF = "Contact:018f0000-0000-7000-8000-00000000c001"


class FakeHubSpot:
    def __init__(self):
        self.rows, self.next_id = {}, 1

    def __call__(self, method, url, params, body):
        if method == "GET" and url.endswith("/crm/v3/objects/contacts"):
            limit = int(params.get("limit", 2))
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
        return Response(404, {})


def payload(record_id="018f0000-0000-7000-8000-00000000c001", **over):
    base = {
        "id": record_id, "tenant_id": TENANT,
        "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted", "lawful_basis": "consent",
        "purpose_id": "p", "retention_policy_id": "r", "full_name": "Asha Rao",
    }
    base.update(over)
    return base


class TestO01ConformanceSandbox(unittest.TestCase):
    def test_certifying_a_connector_does_not_pollute_it(self):
        node = SimulatedConnector("hubspot", "sales", page_size=2)
        node.seed("Contact", payload())
        before = node.count("Contact")
        report = conformance.run_conformance(node)
        self.assertTrue(report.ok, report.summary())
        self.assertEqual(node.count("Contact"), before,
                         "the suite wrote test records into the node it certified")

    def test_the_sandbox_can_be_turned_off(self):
        node = SimulatedConnector("hubspot", "sales", page_size=2)
        before = node.count("Contact")
        conformance.run_conformance(node, sandbox=False)
        self.assertGreater(node.count("Contact"), before,
                           "without the sandbox the writes are visible, which is why it exists")


class TestO02DurableIdentity(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-o02-")
        self.api = FakeHubSpot()
        self.identity = os.path.join(self.dir, "identity.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def node(self):
        return HubSpotConnector("hubspot", RecordedTransport(self.api), TENANT,
                                token="t", page_size=10, identity_path=self.identity)

    def test_the_same_record_written_twice_is_one_external_record(self):
        node = self.node()
        first = node.write("Contact", payload(), "key-1")
        second = node.write("Contact", payload(full_name="Asha R Rao"), "key-2")
        self.assertEqual(first.external_id, second.external_id)
        self.assertEqual(len(self.api.rows), 1)

    def test_the_identity_survives_a_restart(self):
        first = self.node()
        created = first.write("Contact", payload(), "key-1")
        # a new process, a new instance, the same identity file
        second = self.node()
        updated = second.write("Contact", payload(full_name="Asha R Rao"), "key-2")
        self.assertEqual(created.external_id, updated.external_id,
                         "without a durable map the restart creates a duplicate")
        self.assertEqual(len(self.api.rows), 1)

    def test_the_identity_file_is_written(self):
        self.node().write("Contact", payload(), "key-1")
        with open(self.identity, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("canonical_to_external", data)
        self.assertEqual(len(data["canonical_to_external"]), 1)

    def test_without_a_path_there_is_no_persistence(self):
        node = HubSpotConnector("hubspot", RecordedTransport(self.api), TENANT,
                                token="t", page_size=10)
        node.write("Contact", payload(), "key-1")
        self.assertFalse(os.path.exists(self.identity))


class TestO07Deletion(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-o07-")
        self.log = EventLog(os.path.join(self.dir, "l.jsonl"))
        self.server = sync.SyncServer(TENANT, self.log)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_deleted_record_reads_empty(self):
        replica = sync.Replica("r1")
        replica.set(REF, "full_name", "Asha Rao")
        replica.delete(REF)
        self.assertEqual(replica.get(REF), {})
        self.assertTrue(replica.is_deleted(REF))

    def test_deletion_converges(self):
        a, b = sync.Replica("r1"), sync.Replica("r2")
        a.set(REF, "full_name", "Asha Rao")
        sync.converge([a, b], self.server)
        b.delete(REF)
        sync.converge([a, b], self.server)
        self.assertTrue(a.is_deleted(REF))
        self.assertTrue(b.is_deleted(REF))

    def test_resurrection_is_explicit_not_a_side_effect(self):
        replica = sync.Replica("r1")
        replica.set(REF, "full_name", "Asha Rao")
        replica.delete(REF)
        replica.set(REF, "full_name", "written while deleted")
        self.assertTrue(replica.is_deleted(REF),
                        "a field write must not resurrect a deleted record")
        replica.undelete(REF)
        self.assertFalse(replica.is_deleted(REF))
        self.assertEqual(replica.get(REF)["full_name"], "written while deleted",
                         "the field values were kept underneath the tombstone")

    def test_deletion_reaches_the_ledger_and_the_projection(self):
        replica = sync.Replica("r1")
        replica.set(REF, "full_name", "Asha Rao")
        sync.sync(replica, self.server)
        replica.delete(REF)
        sync.sync(replica, self.server)
        actions = [e["action"] for e in self.log.events(TENANT)]
        self.assertIn("sync.delete", actions)
        rebuilt = Projection(self.log, TENANT).build()
        self.assertIsNone(rebuilt.get("Contact", REF.split(":")[1]),
                          "a sync deletion must leave the projection")

    def test_the_chain_verifies_after_a_deletion(self):
        replica = sync.Replica("r1")
        replica.set(REF, "full_name", "x")
        replica.delete(REF)
        sync.sync(replica, self.server)
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)

    def test_deleted_refs_are_listed(self):
        replica = sync.Replica("r1")
        replica.set(REF, "full_name", "x")
        replica.delete(REF)
        self.assertEqual(replica.deleted_refs(), [REF])


if __name__ == "__main__":
    unittest.main()
