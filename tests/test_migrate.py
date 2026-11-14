import os
import shutil
import tempfile
import unittest

from tessera import bulk, migrate
from tessera.ledger import EventLog
from tessera.projection import Projection

TENANT = "018f0000-0000-7000-8000-000000000001"
DEFAULTS = {
    "tenant_id": TENANT, "tx_time": "2026-11-01T09:00:01Z",
    "consent_state": "granted", "lawful_basis": "consent",
    "purpose_id": "p", "retention_policy_id": "r",
}

HUBSPOT = """Record ID,First Name,Last Name,Email,Phone Number,Job Title,Company Name,Owner,Created At
1001,Asha,Rao,asha@example.com,+91 90000 00001,Director,Acme,priya,2026-11-01T09:00:00Z
1002,Ravi,Kumar,ravi@example.com,,Engineer,Globex,sam,2026-11-02T09:00:00Z
"""

SALESFORCE = """Id,Name,Email,Phone,Website,Industry,Created Date
003a,Asha Rao,asha@example.com,+91 90000 00001,acme.example,Software,2026-11-01T09:00:00Z
"""

ZENDESK = """Zendesk ID,Name,Email,Phone,Created At
501,Meera Iyer,meera@example.com,+91 90000 00002,2026-11-03T09:00:00Z
"""

DEALS = """Deal Name,Amount,Currency,Deal Stage,Close Date,Created At
Renewal 2026,45000,INR,proposal,2026-12-01,2026-11-01T09:00:00Z
"""


class TestAutoMap(unittest.TestCase):
    def test_hubspot_headers(self):
        headers = HUBSPOT.splitlines()[0].split(",")
        mapping = migrate.auto_map(headers, "Contact")
        self.assertEqual(mapping.columns["Email"], "email")
        self.assertEqual(mapping.columns["Phone Number"], "phone")
        self.assertIn("full_name", mapping.composites)
        self.assertEqual(mapping.source_ids, ["Record ID"])

    def test_the_composite_joins_first_and_last(self):
        headers = HUBSPOT.splitlines()[0].split(",")
        mapping = migrate.auto_map(headers, "Contact")
        self.assertEqual(mapping.composites["full_name"], ("First Name", "Last Name"))

    def test_coverage_is_reported(self):
        headers = HUBSPOT.splitlines()[0].split(",")
        coverage = migrate.auto_map(headers, "Contact").coverage
        self.assertGreaterEqual(coverage["percent"], 90.0, coverage)
        self.assertEqual(coverage["missing"], [])

    def test_unmapped_columns_are_listed_not_hidden(self):
        headers = HUBSPOT.splitlines()[0].split(",")
        mapping = migrate.auto_map(headers, "Contact")
        for column in ("Job Title", "Company Name", "Owner"):
            self.assertIn(column, mapping.unmapped)

    def test_salesforce_headers(self):
        headers = SALESFORCE.splitlines()[0].split(",")
        mapping = migrate.auto_map(headers, "Contact")
        self.assertEqual(mapping.columns["Name"], "full_name")
        self.assertEqual(mapping.columns["Email"], "email")

    def test_zendesk_headers(self):
        headers = ZENDESK.splitlines()[0].split(",")
        mapping = migrate.auto_map(headers, "Contact")
        self.assertEqual(mapping.columns["Name"], "full_name")
        self.assertIn("Zendesk ID", mapping.source_ids)

    def test_all_three_sources_clear_ninety_percent(self):
        for text in (HUBSPOT, SALESFORCE, ZENDESK):
            headers = text.splitlines()[0].split(",")
            coverage = migrate.auto_map(headers, "Contact").coverage
            self.assertGreaterEqual(coverage["percent"], 90.0, f"{headers}: {coverage}")

    def test_an_object_with_no_map(self):
        with self.assertRaises(bulk.BulkError):
            migrate.auto_map(["a"], "Wombat")


class TestTransform(unittest.TestCase):
    def test_composites_are_joined(self):
        mapping = migrate.auto_map(HUBSPOT.splitlines()[0].split(","), "Contact")
        out = migrate.transform(HUBSPOT, mapping)
        self.assertIn("Asha Rao", out)
        self.assertIn("Ravi Kumar", out)

    def test_money_is_scaled_to_minor_units(self):
        mapping = migrate.auto_map(DEALS.splitlines()[0].split(","), "Deal")
        out = migrate.transform(DEALS, mapping)
        self.assertIn("4500000", out)

    def test_the_output_has_canonical_headers(self):
        mapping = migrate.auto_map(HUBSPOT.splitlines()[0].split(","), "Contact")
        out = migrate.transform(HUBSPOT, mapping)
        header = out.splitlines()[0]
        self.assertIn("full_name", header)
        self.assertNotIn("First Name", header)

    def test_a_bad_amount_does_not_crash_the_transform(self):
        text = "Deal Name,Amount,Currency\nX,not-a-number,INR\n"
        mapping = migrate.auto_map(text.splitlines()[0].split(","), "Deal")
        out = migrate.transform(text, mapping)
        self.assertIn("X", out)


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-migrate-")
        self.log = EventLog(os.path.join(self.dir, "ledger.jsonl"))
        self.migration = migrate.Migration(self.log, TENANT)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_prepare_writes_nothing(self):
        result = self.migration.prepare(HUBSPOT, "Contact", DEFAULTS)
        self.assertEqual(result["preview"]["ready"], 2)
        self.assertEqual(list(self.log.events(TENANT)), [])

    def test_prepare_reports_the_same_number_the_commit_will(self):
        result = self.migration.prepare(HUBSPOT, "Contact", DEFAULTS)
        committed = self.migration.commit(HUBSPOT, "Contact", DEFAULTS)
        self.assertEqual(result["preview"]["ready"], committed["imported"])

    def test_commit_imports(self):
        result = self.migration.commit(HUBSPOT, "Contact", DEFAULTS)
        self.assertEqual(result["imported"], 2)
        rebuilt = Projection(self.log, TENANT).build()
        self.assertEqual(rebuilt.count("Contact"), 2)

    def test_rollback_restores_the_prior_state_exactly(self):
        self.migration.commit(ZENDESK, "Contact", DEFAULTS)
        before = Projection(self.log, TENANT).build().fingerprint()
        result = self.migration.commit(HUBSPOT, "Contact", DEFAULTS)
        self.assertEqual(Projection(self.log, TENANT).build().count("Contact"), 3)
        self.migration.rollback(result["batch"])
        after = Projection(self.log, TENANT).build()
        self.assertEqual(after.count("Contact"), 1)
        self.assertEqual(after.fingerprint(), before,
                         "rollback must restore the pre-migration state exactly")

    def test_the_migration_is_logged(self):
        result = self.migration.commit(HUBSPOT, "Contact", DEFAULTS)
        self.migration.rollback(result["batch"])
        actions = [e["action"] for e in self.log.events(TENANT)]
        self.assertIn("migration.committed", actions)
        self.assertIn("migration.rolled_back", actions)

    def test_a_second_migration_does_not_reuse_the_first_files_mapping(self):
        self.migration.commit(ZENDESK, "Contact", DEFAULTS)
        result = self.migration.commit(HUBSPOT, "Contact", DEFAULTS)
        self.assertEqual(result["imported"], 2,
                         "the second file must be mapped on its own headers")

    def test_the_chain_verifies(self):
        self.migration.commit(HUBSPOT, "Contact", DEFAULTS)
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)


class TestShortcuts(unittest.TestCase):
    def test_a_known_shortcut(self):
        self.assertEqual(migrate.translate_shortcut("hubspot", "c"), "n")

    def test_an_unknown_shortcut_is_returned_unchanged(self):
        self.assertEqual(migrate.translate_shortcut("hubspot", "ctrl+q"), "ctrl+q")

    def test_an_unknown_source(self):
        with self.assertRaises(bulk.BulkError):
            migrate.translate_shortcut("wombat", "c")

    def test_every_source_has_a_map(self):
        self.assertEqual(set(migrate.SHORTCUTS), set(migrate.SOURCES))


class TestGallery(unittest.TestCase):
    def test_the_gallery_lists_templates(self):
        self.assertEqual(len(migrate.gallery()), 3)

    def test_install(self):
        result = migrate.install_template("pipeline.agency")
        self.assertTrue(result["installed"])
        self.assertIn("stages", result)

    def test_an_unknown_template(self):
        with self.assertRaises(bulk.BulkError):
            migrate.install_template("nope")


if __name__ == "__main__":
    unittest.main()
