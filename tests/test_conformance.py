import unittest

from tessera import conformance
from tessera.connectors import BrokenConnector, NativeConnector, SimulatedConnector


class TestConformingConnectors(unittest.TestCase):
    def test_native_passes(self):
        report = conformance.run_conformance(NativeConnector(page_size=2))
        self.assertTrue(report.ok, report.summary())

    def test_simulated_passes(self):
        report = conformance.run_conformance(SimulatedConnector("hubspot", "sales"))
        self.assertTrue(report.ok, report.summary())

    def test_assert_conforms_returns_the_report(self):
        report = conformance.assert_conforms(NativeConnector())
        self.assertTrue(report.ok)
        self.assertGreaterEqual(len(report.checks), 12)

    def test_report_names_every_check(self):
        report = conformance.run_conformance(NativeConnector())
        names = {c.name for c in report.checks}
        for expected in ("capabilities_present", "schema_maps_only_canonical_fields",
                         "read_pagination_terminates", "write_is_idempotent",
                         "round_trip", "errors_are_from_the_taxonomy"):
            self.assertIn(expected, names)


class TestSuiteRejectsViolations(unittest.TestCase):
    """A conformance suite that only ever passes is a rubber stamp."""

    def failing(self, mode):
        report = conformance.run_conformance(BrokenConnector(mode))
        self.assertFalse(report.ok, f"mode {mode} should have failed")
        return {c.name for c in report.failures}

    def test_missing_capabilities(self):
        self.assertIn("capabilities_present", self.failing("no_capabilities"))

    def test_non_canonical_schema_field(self):
        self.assertIn("schema_maps_only_canonical_fields", self.failing("bad_schema"))

    def test_invalid_record(self):
        self.assertIn("read_returns_valid_records", self.failing("bad_record"))

    def test_pagination_that_never_ends(self):
        self.assertIn("read_pagination_terminates", self.failing("no_pagination"))

    def test_non_idempotent_write(self):
        self.assertIn("write_is_idempotent", self.failing("non_idempotent_write"))

    def test_invalid_health(self):
        self.assertIn("health_is_valid", self.failing("bad_health"))

    def test_zero_rate_limit(self):
        self.assertIn("rate_limit_is_positive", self.failing("no_rate_limit"))

    def test_negative_cost(self):
        self.assertIn("cost_estimate_non_negative", self.failing("negative_cost"))

    def test_error_outside_the_taxonomy(self):
        self.assertIn("errors_are_from_the_taxonomy", self.failing("wrong_error"))

    def test_summary_names_the_failures(self):
        report = conformance.run_conformance(BrokenConnector("bad_health"))
        self.assertIn("FAIL", report.summary())
        self.assertIn("health_is_valid", report.summary())


if __name__ == "__main__":
    unittest.main()
