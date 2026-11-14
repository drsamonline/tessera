import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from tessera import bulk, canonical, escape, views
from tessera.api import Principal
from tessera.ledger import EventLog
from tessera.projection import Projection

TENANT = "018f0000-0000-7000-8000-000000000001"
ADMIN = Principal("root", ("admin",), role="admin")
REP = Principal("rep", ("read",), role="rep")

CSV = """name,email,phone
Asha Rao,asha@example.com,+91 90000 00001
Ravi Kumar,ravi@example.com,
,missing@example.com,
"""

MAP = {"name": "full_name", "email": "email", "phone": "phone"}

DEFAULTS = {
    "tenant_id": TENANT, "valid_from": "2026-11-01T09:00:00Z",
    "tx_time": "2026-11-01T09:00:01Z", "consent_state": "granted",
    "lawful_basis": "consent", "purpose_id": "p", "retention_policy_id": "r",
}


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-boring-")
        self.log = EventLog(os.path.join(self.dir, "ledger.jsonl"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class TestCsvImport(Case):
    def test_preview_writes_nothing(self):
        result = bulk.preview(CSV, "Contact", MAP, DEFAULTS)
        self.assertEqual(result["ready"], 2)
        self.assertEqual(result["rejected"], 1, "a row with no name is rejected")
        self.assertEqual(list(self.log.events(TENANT)), [])

    def test_preview_reports_the_problem_row(self):
        result = bulk.preview(CSV, "Contact", MAP, DEFAULTS)
        self.assertEqual(result["problems"][0]["row"], 4)
        self.assertTrue(any("full_name" in i for i in result["problems"][0]["issues"]))

    def test_commit_imports_the_valid_rows(self):
        importer = bulk.Importer(self.log, TENANT)
        result = importer.commit(CSV, "Contact", MAP, defaults=DEFAULTS)
        self.assertEqual(result["imported"], 2)
        self.assertEqual(result["rejected"], 1)
        events = [e for e in self.log.events(TENANT) if e["action"] == "contact.import"]
        self.assertEqual(len(events), 2)

    def test_commit_leaves_a_chain_that_verifies(self):
        bulk.Importer(self.log, TENANT).commit(CSV, "Contact", MAP, defaults=DEFAULTS)
        ok, problems = self.log.verify()
        self.assertTrue(ok, problems)

    def test_rollback_removes_the_batch(self):
        importer = bulk.Importer(self.log, TENANT)
        result = importer.commit(CSV, "Contact", MAP, defaults=DEFAULTS)
        rolled = importer.rollback(result["batch"])
        self.assertEqual(rolled["rolled_back"], 2)
        rebuilt = Projection(self.log, TENANT).build()
        self.assertEqual(rebuilt.count("Contact"), 0)

    def test_rollback_of_an_unknown_batch(self):
        with self.assertRaises(bulk.BulkError):
            bulk.Importer(self.log, TENANT).rollback("nope")

    def test_unknown_object(self):
        with self.assertRaises(bulk.BulkError):
            bulk.preview(CSV, "Wombat", MAP, DEFAULTS)


class TestBulkUpdate(Case):
    def test_apply_writes_one_event_per_record(self):
        bulk_update = bulk.BulkUpdate(self.log, TENANT)
        refs = ["Contact:018f0000-0000-7000-8000-00000000c001",
                "Contact:018f0000-0000-7000-8000-00000000c002"]
        result = bulk_update.apply(refs, "consent_state", "granted")
        self.assertEqual(result["changed"], 2)
        events = [e for e in self.log.events(TENANT) if e["action"] == "bulk.update"]
        self.assertEqual(len(events), 2)

    def test_undo_restores_the_prior_values(self):
        bulk_update = bulk.BulkUpdate(self.log, TENANT)
        ref = "Contact:018f0000-0000-7000-8000-00000000c001"
        result = bulk_update.apply([ref], "full_name", "Wrong Name")
        undone = bulk_update.undo(result["token"], {ref: "Asha Rao"})
        self.assertEqual(undone["restored"], 1)
        rebuilt = Projection(self.log, TENANT).build()
        self.assertEqual(rebuilt.get("Contact", ref.split(":")[1])["full_name"], "Asha Rao")

    def test_an_empty_bulk_operation_is_refused(self):
        with self.assertRaises(bulk.BulkError):
            bulk.BulkUpdate(self.log, TENANT).apply([], "full_name", "x")

    def test_an_unknown_undo_token(self):
        with self.assertRaises(bulk.BulkError):
            bulk.BulkUpdate(self.log, TENANT).undo("nope", {})


class TestBackup(Case):
    def setUp(self):
        super().setUp()
        for i in range(3):
            self.log.append(TENANT, "system", "contact.sync",
                            {"record": dict(DEFAULTS, id=f"018f0000-0000-7000-8000-00000000c00{i}",
                                            full_name=f"Person {i}")},
                            canonical_ref=f"Contact:018f0000-0000-7000-8000-00000000c00{i}")

    def test_backup_carries_a_checksum(self):
        bundle = bulk.Backup(self.log, TENANT).create()
        self.assertEqual(bundle["count"], 3)
        self.assertEqual(len(bundle["checksum"]), 64)

    def test_restore_reproduces_the_chain(self):
        blob = bulk.Backup(self.log, TENANT).to_bytes()
        path = os.path.join(self.dir, "restored.jsonl")
        result = bulk.Backup(self.log, TENANT).restore(blob, path)
        self.assertEqual(result["restored"], 3)
        restored = EventLog(path)
        ok, problems = restored.verify()
        self.assertTrue(ok, problems)

    def test_a_forged_backup_is_refused(self):
        bundle = bulk.Backup(self.log, TENANT).create()
        bundle["events"][0]["payload"]["record"]["full_name"] = "Forged"
        blob = json.dumps(bundle, sort_keys=True).encode("utf-8")
        with self.assertRaises(bulk.BulkError):
            bulk.Backup(self.log, TENANT).restore(blob, os.path.join(self.dir, "x.jsonl"))

    def test_a_point_in_time_backup(self):
        bundle = bulk.Backup(self.log, TENANT).create(upto_sequence=2)
        self.assertEqual(bundle["count"], 2)


class TestSavedViews(unittest.TestCase):
    def records(self):
        return [
            {"full_name": "Asha Rao", "stage": "won", "amount_minor": 500},
            {"full_name": "Ravi Kumar", "stage": "lost", "amount_minor": 100},
            {"full_name": "Meera Iyer", "stage": "won", "amount_minor": 900},
        ]

    def test_a_view_filters(self):
        view = views.SavedView("won", "Deal", condition="stage == 'won'")
        self.assertEqual(len(view.apply(self.records())), 2)

    def test_a_view_sorts_and_limits(self):
        view = views.SavedView("top", "Deal", sort_by="amount_minor",
                               descending=True, limit=2)
        rows = view.apply(self.records())
        self.assertEqual([r["amount_minor"] for r in rows], [900, 500])

    def test_a_record_missing_the_field_does_not_match(self):
        view = views.SavedView("won", "Deal", condition="stage == 'won'")
        self.assertEqual(view.apply([{"full_name": "no stage"}]), [])

    def test_a_view_with_a_bad_condition_is_refused(self):
        with self.assertRaises(Exception):
            views.SavedView("bad", "Deal", condition="stage ==")

    def test_the_store_keeps_views_by_name(self):
        store = views.ViewStore()
        store.save(views.SavedView("won", "Deal", condition="stage == 'won'"))
        self.assertEqual(store.names(), ["won"])
        self.assertEqual(store.get("won").name, "won")

    def test_an_unknown_view(self):
        with self.assertRaises(views.ViewError):
            views.ViewStore().get("nope")


class TestReports(unittest.TestCase):
    def records(self):
        return [
            {"stage": "won", "amount_minor": 500},
            {"stage": "won", "amount_minor": 900},
            {"stage": "lost", "amount_minor": 100},
        ]

    def test_count_by_group(self):
        rows = views.Report("Deal", group_by="stage").run(self.records())
        self.assertEqual(rows[0], {"group": "lost", "count": 1, "value": 1})

    def test_sum_by_group(self):
        rows = views.Report("Deal", group_by="stage", aggregate="sum",
                            field_name="amount_minor").run(self.records())
        won = [r for r in rows if r["group"] == "won"][0]
        self.assertEqual(won["value"], 1400)

    def test_mean_by_group(self):
        rows = views.Report("Deal", group_by="stage", aggregate="mean",
                            field_name="amount_minor").run(self.records())
        won = [r for r in rows if r["group"] == "won"][0]
        self.assertEqual(won["value"], 700)

    def test_a_filter_narrows_the_report(self):
        rows = views.Report("Deal", group_by="stage", condition="amount_minor > 200") \
            .run(self.records())
        self.assertEqual(len(rows), 1)

    def test_an_aggregate_needs_a_field(self):
        with self.assertRaises(views.ViewError):
            views.Report("Deal", group_by="stage", aggregate="sum")

    def test_unknown_aggregate(self):
        with self.assertRaises(views.ViewError):
            views.Report("Deal", group_by="stage", aggregate="median")

    def test_csv_export(self):
        text = views.Report("Deal", group_by="stage").to_csv(self.records())
        self.assertIn("stage,count,count", text)
        self.assertIn("won,2,2", text)


class TestEscapeHatches(Case):
    def setUp(self):
        super().setUp()
        self.log.append(TENANT, "system", "contact.sync",
                        {"record": dict(DEFAULTS, id="018f0000-0000-7000-8000-00000000c001",
                                        full_name="Asha Rao", email="asha@example.com")},
                        canonical_ref="Contact:018f0000-0000-7000-8000-00000000c001")
        self.hatches = escape.EscapeHatch(log=self.log, tenant_id=TENANT,
                                          projection=Projection(self.log, TENANT).build())

    def test_schema_export(self):
        result = self.hatches.schema_export(ADMIN)
        self.assertEqual(result["version"], canonical.SCHEMA_VERSION)
        self.assertIn("Contact", result["objects"])

    def test_record_export_returns_every_field(self):
        rows = self.hatches.record_export(ADMIN, "Contact")
        self.assertEqual(len(rows), 1)
        self.assertIn("email", rows[0])

    def test_query_select_star(self):
        result = self.hatches.query(ADMIN, "SELECT * FROM Contact")
        self.assertEqual(result["count"], 1)

    def test_query_projects_fields(self):
        result = self.hatches.query(ADMIN, "SELECT full_name FROM Contact")
        self.assertEqual(list(result["rows"][0]), ["full_name"])

    def test_query_with_where_and_limit(self):
        result = self.hatches.query(
            ADMIN, "SELECT * FROM Contact WHERE full_name == 'Asha Rao' LIMIT 1")
        self.assertEqual(result["count"], 1)
        none = self.hatches.query(
            ADMIN, "SELECT * FROM Contact WHERE full_name == 'Nobody'")
        self.assertEqual(none["count"], 0)

    def test_query_rejects_anything_but_select(self):
        for hostile in ("DELETE FROM Contact", "DROP TABLE Contact",
                        "SELECT * FROM Contact; DROP TABLE Contact",
                        "UPDATE Contact SET email = 'x'"):
            with self.assertRaises(escape.EscapeDenied, msg=hostile):
                self.hatches.query(ADMIN, hostile)

    def test_break_glass_needs_a_reason(self):
        with self.assertRaises(escape.EscapeDenied):
            self.hatches.break_glass(ADMIN, "fix")

    def test_break_glass_grant_expires_by_clock(self):
        grant = self.hatches.break_glass(ADMIN, "investigating a data incident", minutes=15)
        self.assertTrue(self.hatches.grant_active(grant["token"]))
        later = datetime.now(timezone.utc) + timedelta(minutes=20)
        self.assertFalse(self.hatches.grant_active(grant["token"], now=later))

    def test_a_window_outside_the_bound_is_refused(self):
        with self.assertRaises(escape.EscapeDenied):
            self.hatches.break_glass(ADMIN, "a legitimate reason here", minutes=600)

    def test_every_hatch_refuses_a_non_admin(self):
        for call in (lambda: self.hatches.schema_export(REP),
                     lambda: self.hatches.record_export(REP, "Contact"),
                     lambda: self.hatches.query(REP, "SELECT * FROM Contact"),
                     lambda: self.hatches.break_glass(REP, "a legitimate reason here")):
            with self.assertRaises(escape.EscapeDenied):
                call()

    def test_every_use_is_audited(self):
        self.hatches.schema_export(ADMIN)
        self.hatches.query(ADMIN, "SELECT * FROM Contact")
        uses = [e for e in self.log.events(TENANT) if e["action"] == "escape.use"]
        self.assertEqual(len(uses), 2)
        self.assertEqual(uses[0]["payload"]["hatch"], "schema_export")

    def test_a_refused_use_is_audited_too(self):
        with self.assertRaises(escape.EscapeDenied):
            self.hatches.query(REP, "SELECT * FROM Contact")
        denied = [e for e in self.log.events(TENANT) if e["action"] == "escape.denied"]
        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0]["payload"]["principal"], "rep")

    def test_four_hatches_are_declared(self):
        self.assertEqual(len(escape.HATCHES), 4)


if __name__ == "__main__":
    unittest.main()
