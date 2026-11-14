import unittest

from tessera import observability
from tessera.observability import Histogram, Registry, check_against_targets


class TestHistogram(unittest.TestCase):
    def test_empty(self):
        snap = Histogram("x").snapshot()
        self.assertEqual(snap["count"], 0)
        self.assertEqual(snap["p95"], 0.0)

    def test_nearest_rank_percentile(self):
        h = Histogram("x")
        for value in range(1, 101):
            h.observe(value)
        self.assertEqual(h.percentile(50), 50)
        self.assertEqual(h.percentile(95), 95)
        self.assertEqual(h.percentile(100), 100)

    def test_single_sample(self):
        h = Histogram("x")
        h.observe(7.0)
        self.assertEqual(h.percentile(95), 7.0)
        self.assertEqual(h.percentile(50), 7.0)

    def test_out_of_range_percentile(self):
        with self.assertRaises(ValueError):
            Histogram("x").percentile(0)

    def test_reservoir_is_bounded_and_deterministic(self):
        a, b = Histogram("x", capacity=10), Histogram("x", capacity=10)
        for h in (a, b):
            for value in range(100):
                h.observe(value)
        self.assertEqual(len(a.samples), 10)
        self.assertEqual(a.samples, b.samples, "two runs must agree")
        self.assertEqual(a.total, 100)
        self.assertEqual(a.overflow, 90)

    def test_snapshot_fields(self):
        h = Histogram("x")
        for value in (1, 2, 3):
            h.observe(value)
        snap = h.snapshot()
        self.assertEqual(snap["min"], 1)
        self.assertEqual(snap["max"], 3)
        self.assertAlmostEqual(snap["mean"], 2.0)


class TestRegistry(unittest.TestCase):
    def test_timer_records_milliseconds(self):
        registry = Registry()
        with registry.timer("work"):
            pass
        row = registry.snapshot()[0]
        self.assertEqual(row["name"], "work")
        self.assertEqual(row["count"], 1)
        self.assertGreaterEqual(row["p95"], 0.0)

    def test_observe_creates_the_histogram(self):
        registry = Registry()
        registry.observe("x", 5.0)
        self.assertEqual(registry.histogram("x").total, 1)

    def test_reset_clears(self):
        registry = Registry()
        registry.observe("x", 1.0)
        registry.reset()
        self.assertEqual(registry.snapshot(), [])


class TestGate(unittest.TestCase):
    def snapshot(self, **rows):
        out = []
        for name, values in rows.items():
            h = Histogram(name)
            for value in values:
                h.observe(value)
            out.append(h.snapshot())
        return out

    def test_pass(self):
        result = check_against_targets(self.snapshot(fast=[1, 2, 3]), {"fast": {"p95": 10}})
        self.assertEqual(result[0]["status"], "pass")

    def test_fail(self):
        result = check_against_targets(self.snapshot(slow=[100, 200, 300]),
                                       {"slow": {"p95": 10}})
        self.assertEqual(result[0]["status"], "fail")
        self.assertIn("p95", result[0]["detail"])

    def test_missing_histogram_is_unmeasured_not_passing(self):
        result = check_against_targets([], {"absent": {"p95": 10}})
        self.assertEqual(result[0]["status"], "unmeasured")

    def test_empty_histogram_is_unmeasured(self):
        result = check_against_targets([Histogram("empty").snapshot()],
                                       {"empty": {"p95": 10}})
        self.assertEqual(result[0]["status"], "unmeasured")


if __name__ == "__main__":
    unittest.main()
