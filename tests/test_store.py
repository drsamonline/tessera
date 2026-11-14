import unittest

from tessera import canonical, store

TENANT = "018f0000-0000-7000-8000-000000000001"
OTHER = "018f0000-0000-7000-8000-000000000002"


def contact(tenant=TENANT, record_id="018f0000-0000-7000-8000-00000000c001", **over):
    payload = {
        "id": record_id, "tenant_id": tenant,
        "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted", "lawful_basis": "consent",
        "purpose_id": "p", "retention_policy_id": "r", "full_name": "Asha Rao",
    }
    payload.update(over)
    return payload


class TestTheDdl(unittest.TestCase):
    def test_the_schema_is_structurally_sound(self):
        self.assertEqual(store.validate(store.schema_ddl()), [])

    def test_every_canonical_object_has_a_table(self):
        sql = store.schema_ddl()
        for name in canonical.SCHEMA:
            self.assertIn(store._table(name), sql, name)

    def test_every_table_is_bi_temporal(self):
        sql = store.schema_ddl()
        for name in canonical.SCHEMA:
            table = store._table(name)
            block = sql.split(f"CREATE TABLE {table} (")[1].split("\n);")[0]
            for column in ("valid_from", "valid_to", "tx_time"):
                self.assertIn(column, block, f"{table}: {column}")

    def test_every_table_forces_row_level_security(self):
        sql = store.schema_ddl()
        for name in canonical.SCHEMA:
            table = store._table(name)
            self.assertIn(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;", sql)
            self.assertIn(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;", sql)

    def test_every_policy_reads_the_session_tenant(self):
        sql = store.schema_ddl()
        self.assertEqual(sql.count("current_setting('tessera.tenant_id')"),
                         2 * len(canonical.SCHEMA),
                         "one USING and one WITH CHECK per table")

    def test_a_missing_force_is_reported(self):
        sql = store.schema_ddl().replace(
            "ALTER TABLE t_contact FORCE ROW LEVEL SECURITY;", "")
        problems = store.validate(sql)
        self.assertTrue(any("t_contact" in p and "not forced" in p for p in problems))

    def test_a_policy_without_with_check_is_reported(self):
        sql = store.schema_ddl().replace(
            "  WITH CHECK (tenant_id = current_setting('tessera.tenant_id')::uuid);", ";")
        problems = store.validate(sql)
        self.assertTrue(any("WITH CHECK" in p for p in problems))

    def test_a_missing_table_is_reported(self):
        sql = store.schema_ddl().split("CREATE TABLE t_deal")[0]
        problems = store.validate(sql)
        self.assertTrue(any("t_deal" in p for p in problems))

    def test_a_missing_index_is_reported(self):
        sql = store.schema_ddl().replace(
            "CREATE INDEX t_contact_tenant_id_idx ON t_contact (tenant_id, id);", "")
        self.assertTrue(any("index" in p for p in store.validate(sql)))

    def test_empty_sql(self):
        self.assertTrue(store.validate(""))


class TestTheRunnableStore(unittest.TestCase):
    def setUp(self):
        self.store = store.SqliteStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_put_and_get(self):
        self.store.put(TENANT, "Contact", contact())
        found = self.store.get(TENANT, "Contact", contact()["id"])
        self.assertEqual(found["full_name"], "Asha Rao")

    def test_a_record_is_invisible_to_another_tenant(self):
        self.store.put(TENANT, "Contact", contact())
        self.assertIsNone(self.store.get(OTHER, "Contact", contact()["id"]),
                          "tenant isolation is the whole point of the policy")
        self.assertEqual(self.store.list(OTHER, "Contact"), [])
        self.assertEqual(self.store.count(OTHER), 0)

    def test_a_record_whose_tenant_does_not_match_the_session_is_refused(self):
        with self.assertRaises(store.StoreError):
            self.store.put(TENANT, "Contact", contact(tenant=OTHER))

    def test_an_invalid_record_is_refused(self):
        bad = contact()
        del bad["full_name"]
        with self.assertRaises(store.StoreError):
            self.store.put(TENANT, "Contact", bad)

    def test_an_unknown_object_is_refused(self):
        with self.assertRaises(store.StoreError):
            self.store.put(TENANT, "Wombat", contact())

    def test_put_is_an_upsert(self):
        self.store.put(TENANT, "Contact", contact())
        self.store.put(TENANT, "Contact", contact(full_name="Asha R Rao"))
        self.assertEqual(self.store.count(TENANT, "Contact"), 1)
        self.assertEqual(self.store.get(TENANT, "Contact", contact()["id"])["full_name"],
                         "Asha R Rao")

    def test_delete_is_tenant_scoped(self):
        self.store.put(TENANT, "Contact", contact())
        self.assertFalse(self.store.delete(OTHER, "Contact", contact()["id"]))
        self.assertTrue(self.store.delete(TENANT, "Contact", contact()["id"]))
        self.assertEqual(self.store.count(TENANT), 0)

    def test_two_tenants_hold_the_same_id_without_colliding(self):
        self.store.put(TENANT, "Contact", contact())
        self.store.put(OTHER, "Contact", contact(tenant=OTHER, full_name="Other Person"))
        self.assertEqual(self.store.get(TENANT, "Contact", contact()["id"])["full_name"],
                         "Asha Rao")
        self.assertEqual(self.store.get(OTHER, "Contact", contact()["id"])["full_name"],
                         "Other Person")

    def test_list_is_ordered_and_scoped(self):
        self.store.put(TENANT, "Contact", contact(record_id="018f0000-0000-7000-8000-00000000c002"))
        self.store.put(TENANT, "Contact", contact(record_id="018f0000-0000-7000-8000-00000000c001"))
        rows = self.store.list(TENANT, "Contact")
        self.assertEqual([r["id"] for r in rows],
                         ["018f0000-0000-7000-8000-00000000c001",
                          "018f0000-0000-7000-8000-00000000c002"])

    def test_a_file_backed_store_survives_reopening(self):
        import os
        import tempfile
        directory = tempfile.mkdtemp(prefix="tessera-store-")
        path = os.path.join(directory, "store.db")
        first = store.SqliteStore(path)
        first.put(TENANT, "Contact", contact())
        first.close()
        second = store.SqliteStore(path)
        try:
            self.assertEqual(second.count(TENANT), 1)
        finally:
            second.close()


if __name__ == "__main__":
    unittest.main()
