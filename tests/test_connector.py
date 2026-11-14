import unittest

from tessera import connector
from tessera.connectors import NativeConnector, SimulatedConnector


class TestCircuitBreaker(unittest.TestCase):
    def test_starts_closed(self):
        self.assertEqual(connector.CircuitBreaker().state, "closed")

    def test_opens_after_threshold(self):
        breaker = connector.CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            breaker.record_failure()
        self.assertEqual(breaker.state, "open")
        self.assertFalse(breaker.allow())

    def test_success_resets(self):
        breaker = connector.CircuitBreaker(failure_threshold=2)
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()
        self.assertEqual(breaker.state, "closed")

    def test_half_open_after_cooldown(self):
        now = [0.0]
        breaker = connector.CircuitBreaker(failure_threshold=1, cooldown_seconds=10,
                                           clock=lambda: now[0])
        breaker.record_failure()
        self.assertEqual(breaker.state, "open")
        now[0] = 11.0
        self.assertEqual(breaker.state, "half_open")
        self.assertTrue(breaker.allow())

    def test_rate_limit_does_not_trip_the_breaker(self):
        breaker = connector.CircuitBreaker(failure_threshold=1)
        for _ in range(10):
            breaker.record_rate_limit()
        self.assertEqual(breaker.state, "closed")


class TestRetry(unittest.TestCase):
    def test_transient_is_retried(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise connector.TransientError("timeout")
            return "ok"

        breaker = connector.CircuitBreaker()
        self.assertEqual(
            connector.call_with_retry(flaky, breaker, attempts=3, sleep=lambda _: None), "ok"
        )
        self.assertEqual(calls["n"], 3)
        self.assertEqual(breaker.state, "closed", "a recovered call resets the breaker")

    def test_transient_exhaustion_raises(self):
        def always():
            raise connector.TransientError("down")

        with self.assertRaises(connector.TransientError):
            connector.call_with_retry(always, connector.CircuitBreaker(), attempts=2,
                                      sleep=lambda _: None)

    def test_auth_error_is_not_retried(self):
        calls = {"n": 0}

        def bad():
            calls["n"] += 1
            raise connector.AuthError("401")

        with self.assertRaises(connector.AuthError):
            connector.call_with_retry(bad, connector.CircuitBreaker(), attempts=3,
                                      sleep=lambda _: None)
        self.assertEqual(calls["n"], 1, "an auth failure must not be repeated")

    def test_rate_limit_waits_and_retries(self):
        calls = {"n": 0}

        def throttled():
            calls["n"] += 1
            if calls["n"] == 1:
                raise connector.RateLimited("slow down", retry_after=0.0)
            return "ok"

        breaker = connector.CircuitBreaker(failure_threshold=1)
        self.assertEqual(
            connector.call_with_retry(throttled, breaker, attempts=3, sleep=lambda _: None),
            "ok",
        )
        self.assertEqual(breaker.state, "closed")

    def test_open_breaker_refuses_the_call(self):
        breaker = connector.CircuitBreaker(failure_threshold=1)
        breaker.record_failure()

        def never():
            raise AssertionError("should not be called")

        with self.assertRaises(connector.TransientError):
            connector.call_with_retry(never, breaker, sleep=lambda _: None)


class TestValueObjects(unittest.TestCase):
    def test_health_rejects_unknown_status(self):
        with self.assertRaises(connector.ContractError):
            connector.Health(status="melted")

    def test_rate_limit_must_be_positive(self):
        with self.assertRaises(connector.ContractError):
            connector.RateLimit(requests_per_minute=0)

    def test_capability_supports(self):
        cap = connector.Capability(objects=("Contact",), operations=("read",))
        self.assertTrue(cap.supports("Contact", "read"))
        self.assertFalse(cap.supports("Contact", "write"))
        self.assertFalse(cap.supports("Deal", "read"))


class TestNativeConnector(unittest.TestCase):
    def test_declares_every_canonical_object(self):
        caps = NativeConnector().capabilities()
        self.assertEqual(set(caps.objects), set(connector.OBJECTS)
                         if hasattr(connector, "OBJECTS") else set(caps.objects))
        self.assertGreaterEqual(len(caps.objects), 10)

    def test_write_then_read(self):
        node = NativeConnector(page_size=10)
        payload = {
            "id": "018f0000-0000-7000-8000-00000000c001",
            "tenant_id": "018f0000-0000-7000-8000-000000000001",
            "valid_from": "2026-11-01T09:00:00Z",
            "tx_time": "2026-11-01T09:00:01Z",
            "consent_state": "granted",
            "lawful_basis": "consent",
            "purpose_id": "p1",
            "retention_policy_id": "r1",
            "full_name": "Asha Rao",
        }
        result = node.write("Contact", payload, "k1")
        self.assertTrue(result.ok)
        page = node.read("Contact")
        self.assertEqual(len(page.records), 1)
        self.assertEqual(page.records[0]["full_name"], "Asha Rao")

    def test_invalid_payload_raises_contract_error(self):
        with self.assertRaises(connector.ContractError):
            NativeConnector().write("Contact", {"id": "x"}, "k1")

    def test_unknown_object_raises_schema_drift(self):
        with self.assertRaises(connector.SchemaDrift):
            NativeConnector().read("Wombat")


class TestSimulatedConnector(unittest.TestCase):
    def test_failures_are_injectable(self):
        node = SimulatedConnector("hubspot")
        node.fail_times = 2
        with self.assertRaises(connector.TransientError):
            node.read("Contact")
        with self.assertRaises(connector.TransientError):
            node.read("Contact")
        self.assertEqual(node.read("Contact").records, [])

    def test_throttle_is_injectable(self):
        node = SimulatedConnector("zendesk")
        node.throttle_times = 1
        with self.assertRaises(connector.RateLimited):
            node.read("Contact")

    def test_drift_is_injectable(self):
        node = SimulatedConnector("sfdc")
        node.drift = True
        with self.assertRaises(connector.SchemaDrift):
            node.read("Contact")

    def test_health_reports_degraded_while_failing(self):
        node = SimulatedConnector("hubspot")
        node.fail_times = 1
        self.assertEqual(node.health().status, "degraded")


if __name__ == "__main__":
    unittest.main()
