import math
import unittest
from datetime import datetime, timedelta, timezone

from tessera import metrics

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


class TestTransforms(unittest.TestCase):
    def test_capability_match(self):
        self.assertEqual(metrics.capability_match(["a", "b"], ["a", "b", "c"]), 1.0)
        self.assertEqual(metrics.capability_match(["a", "b"], ["a"]), 0.5)
        self.assertEqual(metrics.capability_match(["a"], []), 0.0)
        self.assertEqual(metrics.capability_match([], ["a"]), 1.0,
                         "an empty requirement matches fully")

    def test_authority_match(self):
        self.assertEqual(metrics.authority_match("authority"), 1.0)
        self.assertEqual(metrics.authority_match("delegate"), 1.0)
        self.assertEqual(metrics.authority_match("bidirectional"), 0.5)
        self.assertEqual(metrics.authority_match("mirror"), 0.2)
        self.assertEqual(metrics.authority_match("nonsense"), 0.0)

    def test_sla_headroom(self):
        assigned = NOW
        deadline = NOW + timedelta(hours=10)
        self.assertAlmostEqual(
            metrics.sla_headroom(deadline, assigned, NOW + timedelta(hours=5)), 0.5
        )
        self.assertEqual(metrics.sla_headroom(deadline, assigned, NOW), 1.0)
        self.assertEqual(metrics.sla_headroom(deadline, assigned, deadline), 0.0)
        self.assertEqual(
            metrics.sla_headroom(deadline, assigned, deadline + timedelta(hours=5)), 0.0,
            "an overdue task has zero headroom, never negative",
        )

    def test_sla_headroom_zero_duration(self):
        self.assertEqual(metrics.sla_headroom(NOW, NOW, NOW), 0.0)

    def test_utilization(self):
        self.assertEqual(metrics.utilization(0, 10), 1.0)
        self.assertEqual(metrics.utilization(5, 10), 0.5)
        self.assertEqual(metrics.utilization(10, 10), 0.0)
        self.assertEqual(metrics.utilization(20, 10), 0.0, "over capacity clamps at zero")
        self.assertEqual(metrics.utilization(5, 0), 0.0, "zero capacity is unusable")

    def test_cost_efficiency(self):
        self.assertEqual(metrics.cost_efficiency(0, 10), 1.0)
        self.assertEqual(metrics.cost_efficiency(5, 10), 0.5)
        self.assertEqual(metrics.cost_efficiency(10, 10), 0.0)
        self.assertEqual(metrics.cost_efficiency(5, 0), 0.0)

    def test_freshness_half_life(self):
        self.assertAlmostEqual(metrics.data_freshness(24, "sales"), 0.5, places=9)
        self.assertAlmostEqual(metrics.data_freshness(4, "support"), 0.5, places=9)
        self.assertAlmostEqual(metrics.data_freshness(0, "sales"), 1.0)
        self.assertLess(metrics.data_freshness(100, "sales"), 0.1)

    def test_freshness_never_exceeds_one(self):
        self.assertEqual(metrics.data_freshness(-5, "sales"), 1.0,
                         "a clock skew must not produce a score above one")

    def test_penalties(self):
        self.assertEqual(metrics.cross_boundary_penalty(True), 1.0)
        self.assertEqual(metrics.cross_boundary_penalty(False), 0.0)
        self.assertEqual(metrics.escalation_penalty(True), 0.3)
        self.assertEqual(metrics.escalation_penalty(False), 0.0)


class TestTrustScore(unittest.TestCase):
    def observations(self, n, **flags):
        return [
            {"at": NOW - timedelta(days=d), "success": True, "escalated": False,
             "conflict": False, "audit_complete": True, **flags}
            for d in range(n)
        ]

    def test_below_minimum_sample_returns_prior(self):
        result = metrics.trust_score(self.observations(19), now=NOW)
        self.assertTrue(result["provisional"])
        self.assertEqual(result["score"], 0.5)
        self.assertEqual(result["sample"], 19)

    def test_at_minimum_sample_is_not_provisional(self):
        result = metrics.trust_score(self.observations(20), now=NOW)
        self.assertFalse(result["provisional"])
        self.assertEqual(result["sample"], 20)

    def test_perfect_record_scores_one(self):
        result = metrics.trust_score(self.observations(30), now=NOW)
        self.assertAlmostEqual(result["score"], 1.0, places=6)

    def test_failures_lower_the_score(self):
        good = metrics.trust_score(self.observations(30), now=NOW)["score"]
        bad = metrics.trust_score(self.observations(30, success=False), now=NOW)["score"]
        self.assertLess(bad, good)

    def test_old_observations_fade(self):
        recent_bad = [
            {"at": NOW - timedelta(days=d), "success": False, "escalated": True,
             "conflict": True, "audit_complete": False} for d in range(20)
        ]
        recent_bad += [
            {"at": NOW - timedelta(days=80 + d), "success": True, "escalated": False,
             "conflict": False, "audit_complete": True} for d in range(20)
        ]
        result = metrics.trust_score(recent_bad, now=NOW)["score"]
        self.assertLess(result, 0.3, "recent failures must dominate old successes")

    def test_observations_outside_window_are_excluded(self):
        old = [{"at": NOW - timedelta(days=200), "success": True, "escalated": False,
                "conflict": False, "audit_complete": True} for _ in range(50)]
        result = metrics.trust_score(old, now=NOW)
        self.assertTrue(result["provisional"])
        self.assertEqual(result["sample"], 0)

    def test_score_always_in_range(self):
        for flags in ({"success": True}, {"success": False}, {"escalated": True},
                      {"conflict": True}, {"audit_complete": False}):
            score = metrics.trust_score(self.observations(25, **flags), now=NOW)["score"]
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)


class TestRvs(unittest.TestCase):
    FIXTURE = [
        ("meeting", NOW - timedelta(days=1)),
        ("call", NOW - timedelta(days=4)),
        ("email", NOW - timedelta(days=11)),
        ("ticket", NOW - timedelta(days=26)),
        ("note", NOW - timedelta(days=60)),
        ("marketing_touch", NOW - timedelta(days=85)),
    ]

    def test_two_implementations_agree_to_six_decimals(self):
        a = metrics.rvs(self.FIXTURE, centrality=0.77, latency_asymmetry=0.42, now=NOW)
        b = metrics.rvs_alt(self.FIXTURE, centrality=0.77, latency_asymmetry=0.42, now=NOW)
        self.assertAlmostEqual(a, b, places=6)

    def test_agreement_holds_on_a_single_interaction(self):
        one = [("meeting", NOW - timedelta(days=7))]
        self.assertAlmostEqual(
            metrics.rvs(one, 1.0, 0.0, now=NOW),
            metrics.rvs_alt(one, 1.0, 0.0, now=NOW),
            places=9,
        )

    def test_decay_half_life(self):
        at_half_life = [("meeting", NOW - timedelta(days=21))]
        score = metrics.rvs(at_half_life, centrality=1.0, latency_asymmetry=0.0, now=NOW)
        self.assertAlmostEqual(score, 0.5, places=9)

    def test_latency_asymmetry_is_capped(self):
        interactions = [("meeting", NOW)]
        capped = metrics.rvs(interactions, 1.0, 3.0, now=NOW)
        beyond = metrics.rvs(interactions, 1.0, 99.0, now=NOW)
        self.assertAlmostEqual(capped, beyond)

    def test_unknown_type_contributes_nothing(self):
        self.assertEqual(metrics.rvs([("telepathy", NOW)], 1.0, 0.0, now=NOW), 0.0)

    def test_empty_history_is_zero(self):
        self.assertEqual(metrics.rvs([], 1.0, 0.0, now=NOW), 0.0)

    def test_normalise_to_p95(self):
        self.assertAlmostEqual(metrics.normalize_to_p95(5.0, 10.0), 0.5)
        self.assertEqual(metrics.normalize_to_p95(5.0, 0.0), 0.0)


class TestForecast(unittest.TestCase):
    def test_stage_probability(self):
        self.assertEqual(metrics.stage_probability(3, 10), 0.3)
        self.assertEqual(metrics.stage_probability(3, 0), 0.0)
        self.assertEqual(metrics.stage_probability(20, 10), 1.0)

    def test_weighted_pipeline_keeps_overrides_visible(self):
        rows = [
            {"amount_minor": 100_000, "probability": 0.5},
            {"amount_minor": 200_000, "probability": 0.5, "override": 0.8},
        ]
        result = metrics.weighted_pipeline(rows)
        self.assertEqual(result["weighted_minor"], 210_000)
        self.assertEqual(result["override_delta_minor"], 60_000,
                         "an override must be reported, not folded away")

    def test_no_rows(self):
        self.assertEqual(metrics.weighted_pipeline([])["weighted_minor"], 0)


if __name__ == "__main__":
    unittest.main()
