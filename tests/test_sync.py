import os
import random
import shutil
import tempfile
import unittest

from tessera import canonical
from tessera.ledger import EventLog
from tessera.sync import Op, Replica, SyncServer, converge, sync

TENANT = "018f0000-0000-7000-8000-000000000001"
REF = "Contact:018f0000-0000-7000-8000-00000000c001"
OTHER = "Contact:018f0000-0000-7000-8000-00000000c002"


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-sync-")
        self.log = EventLog(os.path.join(self.dir, "ledger.jsonl"))
        self.server = SyncServer(TENANT, self.log)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class TestLocalFirst(Case):
    def test_a_write_lands_locally_before_any_sync(self):
        replica = Replica("r1")
        replica.set(REF, "full_name", "Asha Rao")
        self.assertEqual(replica.get(REF)["full_name"], "Asha Rao")
        self.assertEqual(len(replica.outbox), 1, "the write is queued, not sent")
        self.assertEqual(self.server.ops, [], "the server has not been consulted")

    def test_a_replica_renders_from_its_own_store(self):
        replica = Replica("r1")
        replica.set(REF, "full_name", "Asha Rao")
        replica.set(REF, "email", "asha@example.com")
        record = replica.record(REF)
        self.assertEqual(record["full_name"], "Asha Rao")
        self.assertEqual(record["id"], "018f0000-0000-7000-8000-00000000c001")

    def test_an_offline_write_reconciles_on_reconnect(self):
        replica = Replica("r1")
        replica.set(REF, "full_name", "Offline Name")
        # no sync: the client is offline
        self.assertEqual(self.server.ops, [])
        result = sync(replica, self.server)
        self.assertEqual(result["accepted"], 1)
        self.assertEqual(len(self.server.ops), 1)
        self.assertEqual(replica.outbox, [])

    def test_a_malformed_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            Replica("r1").set("Contact", "full_name", "x")


class TestNoLostUpdate(Case):
    def test_two_replicas_writing_different_fields_both_survive(self):
        a, b = Replica("r1"), Replica("r2")
        a.set(REF, "full_name", "Asha Rao")
        b.set(REF, "email", "asha@example.com")
        converge([a, b], self.server)
        for replica in (a, b):
            self.assertEqual(replica.get(REF)["full_name"], "Asha Rao")
            self.assertEqual(replica.get(REF)["email"], "asha@example.com")

    def test_two_replicas_writing_the_same_field_converge_on_one_value(self):
        a, b = Replica("r1"), Replica("r2")
        a.set(REF, "full_name", "From A")
        b.set(REF, "full_name", "From B")
        converge([a, b], self.server)
        self.assertEqual(a.get(REF)["full_name"], b.get(REF)["full_name"])

    def test_the_losing_write_is_still_in_the_operation_log(self):
        a, b = Replica("r1"), Replica("r2")
        a.set(REF, "full_name", "From A")
        b.set(REF, "full_name", "From B")
        converge([a, b], self.server)
        values = [op.value for op in self.server.ops if op.field_name == "full_name"]
        self.assertEqual(sorted(values), ["From A", "From B"],
                         "the loser is not deleted, it is outranked")

    def test_the_tiebreak_is_the_replica_id_and_it_is_total(self):
        low = Op(id="1", replica_id="r1", ref=REF, field_name="f", value="low", lamport=5)
        high = Op(id="2", replica_id="r2", ref=REF, field_name="f", value="high", lamport=5)
        self.assertTrue(high.wins_over(low))
        self.assertFalse(low.wins_over(high))

    def test_a_higher_lamport_wins_over_a_higher_replica_id(self):
        early = Op(id="1", replica_id="r9", ref=REF, field_name="f", value="a", lamport=3)
        late = Op(id="2", replica_id="r1", ref=REF, field_name="f", value="b", lamport=4)
        self.assertTrue(late.wins_over(early))


class TestConvergence(Case):
    def test_a_thousand_mutations_converge(self):
        replicas = [Replica(f"r{i}") for i in range(1, 4)]
        rng = random.Random(1234)
        refs = [REF, OTHER]
        fields = ["full_name", "email", "phone", "stage"]
        for _ in range(1000):
            replica = rng.choice(replicas)
            replica.set(rng.choice(refs), rng.choice(fields),
                        f"v{rng.randrange(1000)}")
        fingerprints = converge(replicas, self.server)
        self.assertEqual(len(set(fingerprints)), 1,
                         "three replicas, one state")

    def test_delivery_order_does_not_change_the_result(self):
        ops = []
        a, b = Replica("r1"), Replica("r2")
        for i in range(20):
            ops.append(a.set(REF, "full_name", f"a{i}"))
            ops.append(b.set(REF, "full_name", f"b{i}"))
        self.server.push(ops)

        forward = Replica("x")
        forward.pull(list(self.server.ops))
        backward = Replica("y")
        backward.pull(list(reversed(self.server.ops)))
        shuffled = Replica("z")
        order = list(self.server.ops)
        random.Random(7).shuffle(order)
        shuffled.pull(order)

        self.assertEqual(forward.fingerprint(), backward.fingerprint())
        self.assertEqual(forward.fingerprint(), shuffled.fingerprint())

    def test_a_replica_that_rejoins_after_a_long_absence_catches_up(self):
        a, b = Replica("r1"), Replica("r2")
        a.set(REF, "full_name", "First")
        sync(a, self.server)
        for i in range(50):
            b.set(REF, "email", f"e{i}@example.com")
        converge([b], self.server)
        sync(a, self.server)
        self.assertEqual(a.get(REF)["email"], b.get(REF)["email"])


class TestIdempotency(Case):
    def test_pushing_the_same_operations_twice_changes_nothing(self):
        replica = Replica("r1")
        replica.set(REF, "full_name", "Once")
        ops = replica.push()
        self.assertEqual(self.server.push(ops), 1)
        self.assertEqual(self.server.push(ops), 0, "the second push is a no-op")
        self.assertEqual(len(self.server.ops), 1)

    def test_applying_the_same_operation_twice_changes_nothing(self):
        replica = Replica("r1")
        op = replica.set(REF, "full_name", "Once")
        other = Replica("r2")
        self.assertEqual(other.pull([op]), 1)
        self.assertEqual(other.pull([op]), 0)
        self.assertEqual(other.get(REF)["full_name"], "Once")

    def test_a_duplicate_does_not_move_the_cursor(self):
        replica = Replica("r1")
        replica.set(REF, "full_name", "x")
        sync(replica, self.server)
        first = replica.cursor
        sync(replica, self.server)
        self.assertEqual(replica.cursor, first)


class TestCursor(Case):
    def test_pull_since_returns_only_new_operations(self):
        a = Replica("r1")
        a.set(REF, "full_name", "one")
        sync(a, self.server)
        cursor = a.cursor
        b = Replica("r2")
        b.set(REF, "email", "two")
        sync(b, self.server)
        incoming, new_cursor = self.server.pull(cursor)
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].field_name, "email")
        self.assertGreater(new_cursor, cursor)


class TestTheLedger(Case):
    def test_every_accepted_operation_is_in_the_ledger(self):
        a, b = Replica("r1"), Replica("r2")
        a.set(REF, "full_name", "A")
        b.set(REF, "email", "b@example.com")
        converge([a, b], self.server)
        events = [e for e in self.log.events(TENANT) if e["action"] == "sync.op"]
        self.assertEqual(len(events), 2)

    def test_the_chain_verifies_after_sync(self):
        a = Replica("r1")
        for i in range(10):
            a.set(REF, "full_name", f"v{i}")
        sync(a, self.server)
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)

    def test_the_ledger_records_the_replica_that_wrote(self):
        a = Replica("laptop-7")
        a.set(REF, "full_name", "x")
        sync(a, self.server)
        event = [e for e in self.log.events(TENANT) if e["action"] == "sync.op"][0]
        self.assertEqual(event["source_node_id"], "laptop-7")


if __name__ == "__main__":
    unittest.main()
