import unittest

from tessera import canonical


VALID_CONTACT = {
    "id": "018f0000-0000-7000-8000-00000000c001",
    "tenant_id": "018f0000-0000-7000-8000-000000000001",
    "valid_from": "2026-11-01T09:00:00Z",
    "tx_time": "2026-11-01T09:00:01Z",
    "consent_state": "granted",
    "lawful_basis": "consent",
    "purpose_id": "sales-outreach",
    "retention_policy_id": "rp-24m",
    "full_name": "Asha Rao",
    "email": "asha@example.com",
}


class TestUuid7(unittest.TestCase):
    def test_shape(self):
        value = canonical.uuid7()
        self.assertEqual(len(value), 36)
        self.assertEqual(value.count("-"), 4)
        self.assertEqual(value[14], "7", "version nibble must be 7")

    def test_variant_bits(self):
        value = canonical.uuid7(rand=bytes(10))
        first_of_clock = int(value.replace("-", "")[16:18], 16)
        self.assertIn(first_of_clock & 0xC0, (0x80,), "variant must be 10xxxxxx")

    def test_time_ordering(self):
        early = canonical.uuid7(ms=1_700_000_000_000, rand=bytes(10))
        late = canonical.uuid7(ms=1_700_000_001_000, rand=bytes(10))
        self.assertLess(early, late, "ids must sort by creation time")
        self.assertEqual(canonical.uuid7_timestamp(late), 1_700_000_001_000)

    def test_bad_rand_length(self):
        with self.assertRaises(ValueError):
            canonical.uuid7(rand=b"short")


class TestValidate(unittest.TestCase):
    def test_valid_payload_passes(self):
        self.assertEqual(canonical.validate("Contact", VALID_CONTACT), [])

    def test_missing_required_field(self):
        payload = dict(VALID_CONTACT)
        del payload["full_name"]
        problems = canonical.validate("Contact", payload)
        self.assertTrue(any("full_name" in p and "missing" in p for p in problems))

    def test_unknown_field_rejected(self):
        payload = dict(VALID_CONTACT, favourite_colour="blue")
        problems = canonical.validate("Contact", payload)
        self.assertTrue(any("favourite_colour" in p for p in problems))

    def test_unknown_object(self):
        problems = canonical.validate("Wombat", {})
        self.assertEqual(len(problems), 1)
        self.assertIn("unknown object", problems[0])

    def test_bad_consent_state(self):
        payload = dict(VALID_CONTACT, consent_state="maybe")
        problems = canonical.validate("Contact", payload)
        self.assertTrue(any("consent_state" in p for p in problems))

    def test_bad_lawful_basis(self):
        payload = dict(VALID_CONTACT, lawful_basis="because")
        problems = canonical.validate("Contact", payload)
        self.assertTrue(any("lawful_basis" in p for p in problems))

    def test_type_mismatch(self):
        payload = dict(VALID_CONTACT, email=42)
        problems = canonical.validate("Contact", payload)
        self.assertTrue(any("expected str" in p for p in problems))

    def test_wrong_id_shape(self):
        payload = dict(VALID_CONTACT, id="not-a-uuid")
        problems = canonical.validate("Contact", payload)
        self.assertTrue(any("expected uuid" in p for p in problems))


class TestHashing(unittest.TestCase):
    def test_key_order_does_not_matter(self):
        a = {"b": 2, "a": 1}
        b = {"a": 1, "b": 2}
        self.assertEqual(canonical.canonical_hash(a), canonical.canonical_hash(b))

    def test_value_change_changes_hash(self):
        a = {"email": "asha@example.com"}
        b = {"email": "asha.rao@example.com"}
        self.assertNotEqual(canonical.canonical_hash(a), canonical.canonical_hash(b))

    def test_hash_is_sha256_hex(self):
        digest = canonical.canonical_hash({"a": 1})
        self.assertEqual(len(digest), 64)
        int(digest, 16)  # raises if not hex


class TestRefs(unittest.TestCase):
    def test_round_trip(self):
        ref = canonical.make_ref("Contact", VALID_CONTACT["id"])
        self.assertEqual(canonical.parse_ref(ref), ("Contact", VALID_CONTACT["id"]))

    def test_unknown_object_rejected(self):
        with self.assertRaises(ValueError):
            canonical.make_ref("Wombat", VALID_CONTACT["id"])

    def test_malformed_ref_rejected(self):
        with self.assertRaises(ValueError):
            canonical.parse_ref("Contact")


if __name__ == "__main__":
    unittest.main()
