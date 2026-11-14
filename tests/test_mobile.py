import json
import os
import shutil
import tempfile
import unittest

from tessera import mobile, sync

TENANT = "018f0000-0000-7000-8000-000000000001"
REF = "Contact:018f0000-0000-7000-8000-00000000c001"
PASSPHRASE = "correct horse battery"


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-mobile-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.dir, name)


class TestKeyCustody(Case):
    def test_the_key_is_derived_not_stored(self):
        vault = mobile.KeyVault(self.path("vault.json"))
        key = vault.derive(PASSPHRASE)
        vault.save()
        self.assertEqual(len(key), 32)
        with open(self.path("vault.json"), encoding="utf-8") as handle:
            blob = json.load(handle)
        self.assertEqual(set(blob), {"version", "kdf", "iterations", "salt", "verifier"})

    def test_the_passphrase_and_the_key_never_reach_the_disk(self):
        vault = mobile.KeyVault(self.path("vault.json"))
        key = vault.derive(PASSPHRASE)
        vault.save()
        for name in os.listdir(self.dir):
            with open(self.path(name), encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn(PASSPHRASE, text, name)
            self.assertNotIn(key.hex(), text, name)

    def test_a_reload_with_the_right_passphrase_derives_the_same_key(self):
        first = mobile.KeyVault(self.path("vault.json"))
        key = first.derive(PASSPHRASE)
        first.save()
        second = mobile.KeyVault.load(self.path("vault.json"), PASSPHRASE)
        self.assertEqual(second.key, key)

    def test_a_wrong_passphrase_is_refused(self):
        vault = mobile.KeyVault(self.path("vault.json"))
        vault.derive(PASSPHRASE)
        vault.save()
        with self.assertRaises(mobile.MobileError):
            mobile.KeyVault.load(self.path("vault.json"), "wrong horse battery")

    def test_a_short_passphrase_is_refused(self):
        with self.assertRaises(mobile.MobileError):
            mobile.KeyVault().derive("short")

    def test_no_key_before_derivation(self):
        with self.assertRaises(mobile.MobileError):
            mobile.KeyVault().key

    def test_two_vaults_use_different_salts(self):
        a, b = mobile.KeyVault(), mobile.KeyVault()
        self.assertNotEqual(a.salt, b.salt)
        self.assertNotEqual(a.derive(PASSPHRASE), b.derive(PASSPHRASE))


class TestTheReferenceConstruction(Case):
    def setUp(self):
        super().setUp()
        self.key = mobile.KeyVault().derive(PASSPHRASE)

    def test_round_trip(self):
        blob = mobile.encrypt(self.key, b"asha@example.com")
        self.assertEqual(mobile.decrypt(self.key, blob), b"asha@example.com")

    def test_the_ciphertext_does_not_contain_the_plaintext(self):
        blob = mobile.encrypt(self.key, b"asha@example.com")
        self.assertNotIn(b"asha", bytes.fromhex(blob["ciphertext"]))

    def test_a_changed_ciphertext_fails(self):
        blob = mobile.encrypt(self.key, b"asha@example.com")
        blob["ciphertext"] = blob["ciphertext"][:-2] + "00"
        with self.assertRaises(mobile.MobileError):
            mobile.decrypt(self.key, blob)

    def test_a_changed_tag_fails(self):
        blob = mobile.encrypt(self.key, b"x")
        blob["tag"] = "0" * 64
        with self.assertRaises(mobile.MobileError):
            mobile.decrypt(self.key, blob)

    def test_a_wrong_key_fails(self):
        blob = mobile.encrypt(self.key, b"x")
        other = mobile.KeyVault().derive("another passphrase")
        with self.assertRaises(mobile.MobileError):
            mobile.decrypt(other, blob)

    def test_a_nonce_is_never_reused(self):
        first = mobile.encrypt(self.key, b"same")
        second = mobile.encrypt(self.key, b"same")
        self.assertNotEqual(first["nonce"], second["nonce"])
        self.assertNotEqual(first["ciphertext"], second["ciphertext"])


class TestTheOutbox(Case):
    def op(self, op_id="op1"):
        return {"id": op_id, "replica_id": "phone", "ref": REF, "field": "full_name",
                "value": "Asha Rao", "lamport": 1, "actor": "human"}

    def test_append_and_pending(self):
        outbox = mobile.OfflineOutbox(self.path("outbox.jsonl"))
        outbox.append(self.op())
        self.assertEqual(outbox.size(), 1)

    def test_a_duplicate_is_ignored(self):
        outbox = mobile.OfflineOutbox(self.path("outbox.jsonl"))
        outbox.append(self.op())
        outbox.append(self.op())
        self.assertEqual(outbox.size(), 1)

    def test_the_outbox_survives_the_process_being_killed(self):
        outbox = mobile.OfflineOutbox(self.path("outbox.jsonl"))
        outbox.append(self.op("op1"))
        outbox.append(self.op("op2"))
        del outbox                       # the app is killed, nothing is closed cleanly
        reopened = mobile.OfflineOutbox(self.path("outbox.jsonl"))
        self.assertEqual(reopened.size(), 2, "an acknowledged write must survive a kill")
        self.assertEqual([op["id"] for op in reopened.pending()], ["op1", "op2"])

    def test_a_torn_last_line_is_dropped_not_fatal(self):
        outbox = mobile.OfflineOutbox(self.path("outbox.jsonl"))
        outbox.append(self.op("op1"))
        with open(self.path("outbox.jsonl"), "a", encoding="utf-8") as handle:
            handle.write('{"id": "op2", "ref":')   # a kill mid-write
        reopened = mobile.OfflineOutbox(self.path("outbox.jsonl"))
        self.assertEqual(reopened.size(), 1)
        self.assertEqual(reopened.pending()[0]["id"], "op1")

    def test_drain_removes_only_the_acknowledged(self):
        outbox = mobile.OfflineOutbox(self.path("outbox.jsonl"))
        for name in ("op1", "op2", "op3"):
            outbox.append(self.op(name))
        removed = outbox.drain(["op1", "op3"])
        self.assertEqual(removed, 2)
        self.assertEqual([op["id"] for op in outbox.pending()], ["op2"])

    def test_an_operation_without_an_id_is_refused(self):
        with self.assertRaises(mobile.MobileError):
            mobile.OfflineOutbox(self.path("o.jsonl")).append({"ref": REF})


class TestSevenDaysOffline(Case):
    def test_a_week_of_absence_loses_nothing(self):
        log_path = self.path("ledger.jsonl")
        from tessera.ledger import EventLog
        log = EventLog(log_path)
        server = sync.SyncServer(TENANT, log)
        replica = sync.Replica("phone")
        outbox = mobile.OfflineOutbox(self.path("outbox.jsonl"))

        # the phone writes while it has no signal
        for i in range(3):
            op = replica.set(REF, "full_name", f"Offline {i}")
            outbox.append(op.to_dict())

        # the world moves on for a week without the phone
        desk = sync.Replica("desk")
        for i in range(10):
            desk.set(REF, "email", f"e{i}@example.com")
            sync.sync(desk, server)

        result = mobile.sync_after_absence(replica, server, outbox, days=7)
        self.assertEqual(result["queued"], 3)
        self.assertEqual(result["remaining"], 0, "the outbox empties on acknowledgement")
        self.assertEqual(replica.cursor, 13, "three of its own plus ten from the desk")

    def test_the_result_matches_a_client_that_never_left(self):
        from tessera.ledger import EventLog
        log = EventLog(self.path("ledger.jsonl"))
        server = sync.SyncServer(TENANT, log)

        away = sync.Replica("away")
        outbox = mobile.OfflineOutbox(self.path("outbox.jsonl"))
        for i in range(3):
            outbox.append(away.set(REF, "full_name", f"v{i}").to_dict())

        desk = sync.Replica("desk")
        for i in range(5):
            desk.set(REF, "email", f"e{i}@example.com")
            sync.sync(desk, server)

        stayed = sync.Replica("stayed")
        sync.sync(stayed, server)
        mobile.sync_after_absence(away, server, outbox, days=7)
        sync.sync(stayed, server)
        self.assertEqual(away.fingerprint(), stayed.fingerprint(),
                         "a client back from a week must land where one that stayed did")

    def test_the_chain_verifies_after_the_absence(self):
        from tessera.ledger import EventLog
        log = EventLog(self.path("ledger.jsonl"))
        server = sync.SyncServer(TENANT, log)
        replica = sync.Replica("phone")
        outbox = mobile.OfflineOutbox(self.path("outbox.jsonl"))
        outbox.append(replica.set(REF, "full_name", "x").to_dict())
        mobile.sync_after_absence(replica, server, outbox)
        ok, problems = log.verify()
        self.assertTrue(ok, problems)


if __name__ == "__main__":
    unittest.main()
