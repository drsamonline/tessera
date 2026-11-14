import unittest

from tessera.connector import RateLimited
from tessera.ratelimit import Budgets, NodeBudget, TokenBucket


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class TestTokenBucket(unittest.TestCase):
    def test_burst_is_available_immediately(self):
        bucket = TokenBucket(rate_per_minute=60, burst=3, clock=Clock())
        self.assertEqual(bucket.wait_time(3), 0.0)
        self.assertTrue(bucket.try_acquire(3))

    def test_refills_at_the_declared_rate(self):
        clock = Clock()
        bucket = TokenBucket(rate_per_minute=60, burst=2, clock=clock)  # 1 token/second
        bucket.try_acquire(2)
        self.assertEqual(bucket.tokens, 0.0)
        clock.advance(1.0)
        self.assertAlmostEqual(bucket.tokens, 1.0, places=6)

    def test_cap_is_the_burst(self):
        clock = Clock()
        bucket = TokenBucket(rate_per_minute=60, burst=2, clock=clock)
        clock.advance(3600)
        self.assertAlmostEqual(bucket.tokens, 2.0, places=6)

    def test_wait_time_is_the_deficit_over_the_rate(self):
        clock = Clock()
        bucket = TokenBucket(rate_per_minute=60, burst=1, clock=clock)
        bucket.try_acquire(1)
        self.assertAlmostEqual(bucket.wait_time(1), 1.0, places=6)

    def test_acquire_raises_with_the_wait(self):
        clock = Clock()
        bucket = TokenBucket(rate_per_minute=60, burst=1, clock=clock)
        bucket.acquire(1)
        with self.assertRaises(RateLimited) as ctx:
            bucket.acquire(1)
        self.assertAlmostEqual(ctx.exception.retry_after, 1.0, places=2)

    def test_acquire_returns_zero_when_immediate(self):
        bucket = TokenBucket(rate_per_minute=60, burst=2, clock=Clock())
        self.assertEqual(bucket.acquire(1), 0.0)

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError):
            TokenBucket(rate_per_minute=0, burst=1)
        with self.assertRaises(ValueError):
            TokenBucket(rate_per_minute=60, burst=0)


class TestNodeBudget(unittest.TestCase):
    def test_admit_and_release(self):
        budget = NodeBudget("hubspot", rate_per_minute=600, burst=5, max_in_flight=2)
        budget.admit()
        budget.admit()
        self.assertEqual(budget.in_flight, 2)
        budget.release()
        self.assertEqual(budget.in_flight, 1)

    def test_in_flight_cap_applies_backpressure(self):
        budget = NodeBudget("hubspot", rate_per_minute=600, burst=5, max_in_flight=1)
        budget.admit()
        with self.assertRaises(RateLimited):
            budget.admit()
        self.assertEqual(budget.rejected, 1)

    def test_queue_cap_applies_backpressure(self):
        budget = NodeBudget("hubspot", rate_per_minute=600, burst=5, max_queue=0)
        budget.queued = 0
        budget.max_queue = 0
        with self.assertRaises(RateLimited):
            budget.admit()

    def test_bucket_exhaustion_applies_backpressure(self):
        clock = Clock()
        budget = NodeBudget("hubspot", rate_per_minute=60, burst=1, max_in_flight=10,
                            clock=clock)
        budget.admit()
        budget.release()
        with self.assertRaises(RateLimited):
            budget.admit()

    def test_snapshot_reports_everything(self):
        budget = NodeBudget("zendesk", rate_per_minute=600, burst=5)
        budget.admit()
        snap = budget.snapshot()
        self.assertEqual(snap["node_id"], "zendesk")
        self.assertEqual(snap["in_flight"], 1)
        self.assertEqual(snap["admitted"], 1)
        self.assertIn("tokens", snap)


class TestBudgets(unittest.TestCase):
    def test_unregistered_node_gets_a_conservative_default(self):
        budgets = Budgets()
        budget = budgets.get("unknown")
        self.assertEqual(budget.rate_per_minute, 100)
        self.assertEqual(budget.max_in_flight, 4)
        self.assertIs(budgets.get("unknown"), budget, "the default is created once")

    def test_registered_budget_is_returned(self):
        budgets = Budgets()
        budgets.register(NodeBudget("hubspot", rate_per_minute=900))
        self.assertEqual(budgets.get("hubspot").rate_per_minute, 900)

    def test_snapshot_lists_every_budget(self):
        budgets = Budgets()
        budgets.register(NodeBudget("a"))
        budgets.register(NodeBudget("b"))
        self.assertEqual({row["node_id"] for row in budgets.snapshot()}, {"a", "b"})


if __name__ == "__main__":
    unittest.main()
