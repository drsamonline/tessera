import unittest

from tessera import conflict


def c(node, value, valid_from="2026-11-01T09:00:00Z", trust=0.5):
    return conflict.Conflict(node, value, valid_from, trust)


class TestResolutionOrder(unittest.TestCase):
    def test_single_source_is_not_a_conflict(self):
        record = conflict.resolve("email", [c("a", "x")])
        self.assertEqual(record["rule"], "single_source")
        self.assertEqual(record["value"], "x")
        self.assertTrue(conflict.is_resolved(record))

    def test_authority_beats_recency(self):
        record = conflict.resolve(
            "email",
            [c("hubspot", "owner@example.com", "2026-11-01T09:00:00Z", 0.4),
             c("zendesk", "later@example.com", "2026-11-02T09:00:00Z", 0.9)],
            authority_map={"hubspot": "authority", "zendesk": "bidirectional"},
        )
        self.assertEqual(record["rule"], "authority_map")
        self.assertEqual(record["value"], "owner@example.com")

    def test_delegate_does_not_claim_ownership(self):
        # `delegate` means the node accepts mesh writes; it is not the field's
        # owner. Only `authority` wins outright.
        record = conflict.resolve(
            "email",
            [c("a", "from-a", trust=0.2), c("b", "from-b", trust=0.8)],
            authority_map={"a": "delegate", "b": "bidirectional"},
        )
        self.assertEqual(record["rule"], "trust_score")
        self.assertEqual(record["winner"], "b")

    def test_two_authorities_fall_through_to_trust(self):
        record = conflict.resolve(
            "email",
            [c("a", "from-a", trust=0.3), c("b", "from-b", trust=0.9)],
            authority_map={"a": "authority", "b": "authority"},
        )
        self.assertEqual(record["rule"], "trust_score")
        self.assertEqual(record["winner"], "b")

    def test_trust_beats_recency(self):
        record = conflict.resolve(
            "email",
            [c("a", "trusted", "2026-11-01T09:00:00Z", 0.9),
             c("b", "recent", "2026-11-05T09:00:00Z", 0.3)],
        )
        self.assertEqual(record["rule"], "trust_score")
        self.assertEqual(record["winner"], "a")

    def test_recency_decides_when_trust_ties(self):
        record = conflict.resolve(
            "email",
            [c("a", "old", "2026-11-01T09:00:00Z", 0.5),
             c("b", "new", "2026-11-05T09:00:00Z", 0.5)],
        )
        self.assertEqual(record["rule"], "bi_temporal_recency")
        self.assertEqual(record["value"], "new")

    def test_field_priority_decides_when_recency_ties(self):
        record = conflict.resolve(
            "email",
            [c("a", "from-a"), c("b", "from-b")],
            field_priority=["email", "phone"],
        )
        self.assertEqual(record["rule"], "field_priority")
        self.assertTrue(conflict.is_resolved(record))

    def test_unresolvable_blocks_the_field_not_the_record(self):
        record = conflict.resolve("email", [c("a", "from-a"), c("b", "from-b")])
        self.assertEqual(record["rule"], "human_review")
        self.assertTrue(record["blocked"])
        self.assertFalse(conflict.is_resolved(record))
        self.assertIsNone(record["value"])

    def test_no_candidates_is_an_error(self):
        with self.assertRaises(ValueError):
            conflict.resolve("email", [])


class TestRecord(unittest.TestCase):
    def test_record_carries_both_candidates(self):
        record = conflict.resolve(
            "email",
            [c("hubspot", "a@example.com", trust=0.4), c("zendesk", "b@example.com", trust=0.9)],
        )
        values = {row["value"] for row in record["candidates"]}
        self.assertEqual(values, {"a@example.com", "b@example.com"})

    def test_event_payload_keeps_the_rule_and_the_losers(self):
        record = conflict.resolve(
            "email",
            [c("hubspot", "a@example.com", trust=0.4), c("zendesk", "b@example.com", trust=0.9)],
        )
        payload = conflict.to_event_payload(record)
        self.assertEqual(payload["rule"], "trust_score")
        self.assertEqual(payload["winner"], "zendesk")
        self.assertEqual(len(payload["candidates"]), 2)

    def test_every_rule_name_is_declared(self):
        record = conflict.resolve("email", [c("a", "x")])
        self.assertIn(record["rule"], conflict.RULES)


if __name__ == "__main__":
    unittest.main()
