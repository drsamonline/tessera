import unittest

from tessera import fuzz, routing


class TestTheFuzzerIsClean(unittest.TestCase):
    """Ten seeds per suite, small counts: fast enough for every run, wide enough
    to catch an ordering bug that only appears on a particular interleaving."""

    def test_ledger(self):
        for seed in range(10):
            self.assertEqual(fuzz.fuzz_ledger(seed, events=20), [], f"seed {seed}")

    def test_sync(self):
        for seed in range(10):
            self.assertEqual(fuzz.fuzz_sync(seed, operations=20), [], f"seed {seed}")

    def test_conflict(self):
        for seed in range(10):
            self.assertEqual(fuzz.fuzz_conflict(seed, rounds=15), [], f"seed {seed}")

    def test_routing(self):
        for seed in range(10):
            self.assertEqual(fuzz.fuzz_routing(seed, rounds=15), [], f"seed {seed}")

    def test_the_whole_report_is_empty(self):
        report = fuzz.run(seeds=4)
        self.assertEqual({name: failures for name, failures in report.items() if failures}, {})


class TestTheFuzzerHasTeeth(unittest.TestCase):
    """A fuzzer that only ever passes is a fuzzer nobody has tested."""

    def test_it_catches_a_ledger_that_does_not_verify(self):
        import tessera.fuzz as module
        saved = module.ledger.EventLog

        class BrokenLog(saved):
            def verify(self, tenant_id=None, anchor=None):
                return True, []          # a verifier that always says yes

        module.ledger.EventLog = BrokenLog
        try:
            failures = fuzz.fuzz_ledger(0, events=5)
            self.assertTrue(failures, "a ledger that always verifies must be caught")
            self.assertTrue(any("not caught" in f for f in failures))
        finally:
            module.ledger.EventLog = saved

    def test_it_catches_a_conflict_resolver_that_is_not_deterministic(self):
        import tessera.fuzz as module
        saved = module.conflict.resolve
        state = {"calls": 0}

        def flaky(field_name, candidates, authority=None):
            state["calls"] += 1
            return {"value": f"v{state['calls'] % 2}", "rule": "trust", "winner": "n0"}

        module.conflict.resolve = flaky
        try:
            failures = fuzz.fuzz_conflict(0, rounds=5)
            self.assertTrue(failures, "a resolver that changes its answer must be caught")
            self.assertTrue(any("not deterministic" in f for f in failures))
        finally:
            module.conflict.resolve = saved


class TestTheRangeInvariant(unittest.TestCase):
    """R-17: the terms are in [0,1]; the total is not, and must not be clamped."""

    def test_the_floor_is_the_penalty_weight(self):
        floor = -routing.weights()["_penalty_weight"]
        self.assertEqual(floor, -0.2)

    def test_a_maximal_penalty_goes_below_zero(self):
        terms = {name: 0.0 for name in routing.weights() if not name.startswith("_")}
        terms["cross_boundary_penalty"] = 1.0
        self.assertLess(routing.score(terms)["score"], 0.0)

    def test_ordering_survives_below_zero(self):
        base = {name: 0.0 for name in routing.weights() if not name.startswith("_")}
        worse = dict(base, cross_boundary_penalty=1.0)
        better = dict(base, cross_boundary_penalty=0.6)
        self.assertLess(routing.score(worse)["score"], routing.score(better)["score"],
                        "clamping to [0,1] would have made these a tie")


if __name__ == "__main__":
    unittest.main()
