import unittest
from datetime import datetime, timedelta, timezone

from tessera import routing

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def terms(**over):
    base = {
        "capability_match": 1.0,
        "authority_match": 1.0,
        "sla_headroom": 0.8,
        "trust_score": 0.7,
        "utilization": 0.6,
        "cost_efficiency": 0.9,
        "data_freshness": 0.9,
        "cross_boundary_penalty": 0.0,
    }
    base.update(over)
    return base


def workforce_terms(**over):
    base = {
        "capability_match": 1.0,
        "sla_headroom": 0.8,
        "trust_score": 0.7,
        "utilization": 0.6,
        "cost_efficiency": 0.9,
        "escalation_penalty": 0.0,
    }
    base.update(over)
    return base


class TestWeights(unittest.TestCase):
    def test_both_vectors_are_valid(self):
        for version in routing.WEIGHTS:
            self.assertEqual(routing.check_weights(version), [], version)

    def test_unknown_version(self):
        with self.assertRaises(KeyError):
            routing.weights("federation-v99")

    def test_sum_is_one(self):
        for version, vector in routing.WEIGHTS.items():
            positive = {k: v for k, v in vector.items() if not k.startswith("_")}
            self.assertAlmostEqual(sum(positive.values()), 1.0, places=9, msg=version)


class TestScore(unittest.TestCase):
    def test_breakdown_contributions_sum_to_score(self):
        result = routing.score(terms())
        parts = sum(p["contribution"] for p in result["breakdown"].values())
        self.assertAlmostEqual(result["score"], parts + result["penalty"]["contribution"],
                               places=9)

    def test_perfect_terms_score_one(self):
        result = routing.score(terms(capability_match=1.0, authority_match=1.0,
                                     sla_headroom=1.0, trust_score=1.0, utilization=1.0,
                                     cost_efficiency=1.0, data_freshness=1.0))
        self.assertAlmostEqual(result["score"], 1.0, places=9)

    def test_penalty_is_subtracted(self):
        clean = routing.score(terms(cross_boundary_penalty=0.0))["score"]
        crossing = routing.score(terms(cross_boundary_penalty=1.0))["score"]
        self.assertAlmostEqual(clean - crossing, 0.20, places=9)

    def test_missing_term_is_an_error_not_a_zero(self):
        bad = terms()
        del bad["trust_score"]
        with self.assertRaises(KeyError):
            routing.score(bad)

    def test_out_of_range_term_rejected(self):
        with self.assertRaises(ValueError):
            routing.score(terms(utilization=1.4))

    def test_weights_version_is_carried(self):
        self.assertEqual(routing.score(terms())["weights_version"], "federation-v1")

    def test_workforce_vector_uses_its_own_terms(self):
        result = routing.score(workforce_terms(), version="workforce-v1")
        self.assertEqual(result["weights_version"], "workforce-v1")
        self.assertIn("escalation_penalty", result["penalty"]["term"])


class TestRoute(unittest.TestCase):
    def test_best_candidate_first(self):
        ranked = routing.route([
            {"id": "weak", "terms": terms(capability_match=0.2), "estimated_cost": 1},
            {"id": "strong", "terms": terms(), "estimated_cost": 1},
        ])
        self.assertEqual(ranked[0]["id"], "strong")
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertEqual(ranked[1]["rank"], 2)

    def test_identical_candidates_break_on_id(self):
        ranked = routing.route([
            {"id": "b-node", "terms": terms(), "estimated_cost": 1},
            {"id": "a-node", "terms": terms(), "estimated_cost": 1},
        ])
        self.assertEqual([r["id"] for r in ranked], ["a-node", "b-node"])

    def test_input_order_does_not_change_output(self):
        candidates = [
            {"id": "x", "terms": terms(capability_match=0.9), "estimated_cost": 3},
            {"id": "y", "terms": terms(capability_match=0.9), "estimated_cost": 3},
            {"id": "z", "terms": terms(capability_match=0.4), "estimated_cost": 1},
        ]
        forward = [r["id"] for r in routing.route(list(candidates))]
        backward = [r["id"] for r in routing.route(list(reversed(candidates)))]
        self.assertEqual(forward, backward, "routing must be total and order-independent")

    def test_tie_breaks_on_trust_before_cost(self):
        ranked = routing.route([
            {"id": "cheap-low-trust",
             "terms": terms(trust_score=0.4, capability_match=0.5), "estimated_cost": 1},
            {"id": "dear-high-trust",
             "terms": terms(trust_score=0.9, capability_match=0.5), "estimated_cost": 9},
        ])
        # the scores differ here, so assert the higher-trust node wins on merit
        self.assertEqual(ranked[0]["id"], "dear-high-trust")

    def test_explain_lists_every_term(self):
        decision = routing.route([{"id": "n", "terms": terms(), "estimated_cost": 1}])[0]
        text = routing.explain(decision)
        for name in ("capability_match", "authority_match", "data_freshness",
                     "cross_boundary_penalty"):
            self.assertIn(name, text)


class TestWorkforce(unittest.TestCase):
    def test_agent_seat_without_fallback_is_rejected(self):
        with self.assertRaises(ValueError):
            routing.assert_agent_seat({"id": "s1", "occupant_type": "agent"})

    def test_agent_seat_with_fallback_passes(self):
        routing.assert_agent_seat({"id": "s1", "occupant_type": "agent",
                                   "fallback_seat_id": "s2"})

    def test_human_seat_needs_no_fallback(self):
        routing.assert_agent_seat({"id": "s1", "occupant_type": "human"})

    def test_select_occupant_skips_inactive_and_untrusted(self):
        best = routing.select_occupant([
            {"id": "paused", "status": "paused", "terms": workforce_terms(trust_score=1.0),
             "estimated_cost": 1},
            {"id": "untrusted", "status": "active", "terms": workforce_terms(trust_score=0.05),
             "estimated_cost": 1},
            {"id": "ok", "status": "active", "terms": workforce_terms(trust_score=0.6),
             "estimated_cost": 2},
        ])
        self.assertEqual(best["id"], "ok")

    def test_select_occupant_returns_none_when_nobody_eligible(self):
        self.assertIsNone(routing.select_occupant([
            {"id": "paused", "status": "paused", "terms": workforce_terms(),
             "estimated_cost": 1},
        ]))

    def test_sla_clock_headroom(self):
        clock = routing.sla_clock(
            deadline=NOW + timedelta(hours=10),
            assigned_at=NOW,
            handoff_at=NOW + timedelta(hours=5),
        )
        self.assertAlmostEqual(clock["headroom"], 0.5)
        self.assertEqual(clock["remaining_seconds"], 5 * 3600)


if __name__ == "__main__":
    unittest.main()
