"""The store: Postgres DDL, its validator, and a runnable SQLite path.

Reference: docs/04-core.md ("Stack") and docs/16-acceptance-criteria.md,
deliverable 2.

Two things live here, and the difference between them is the honest part:

**`schema_ddl()`** generates the Postgres DDL for the ten canonical objects -
bi-temporal columns on every table, row-level security enabled and forced, and a
tenant policy on each. `validate()` reads that SQL back and asserts the four
things the acceptance criterion asks for. No server is needed to generate or to
check it, and no server was available: this environment ships the Postgres
*client* and not the server.

**`SqliteStore`** is the same contract, runnable, with tenant isolation enforced
on every statement. It exists so the store's behaviour is tested rather than
described. It is not a Postgres substitute and does not pretend to be one: SQLite
has no row-level security, so isolation is a property of the queries here rather
than of the engine.

What is missing is stated in docs/39-postgres.md: the DDL has never been executed
against a server, and there are no Django models.
"""

from __future__ import annotations

import json
import re
import sqlite3

from . import canonical

ENVELOPE_COLUMNS = (
    "id", "tenant_id", "valid_from", "valid_to", "tx_time", "created_at",
    "updated_at", "owner_seat_id",
)

TENANT_SETTING = "tessera.tenant_id"


def _columns(object_name: str) -> list[tuple[str, str]]:
    """Envelope columns plus the object's own, as (name, postgres type)."""
    columns = [
        ("id", "uuid PRIMARY KEY"),
        ("tenant_id", "uuid NOT NULL"),
        ("valid_from", "timestamptz"),
        ("valid_to", "timestamptz"),
        ("tx_time", "timestamptz NOT NULL"),
        ("created_at", "timestamptz NOT NULL DEFAULT now()"),
        ("updated_at", "timestamptz NOT NULL DEFAULT now()"),
        ("owner_seat_id", "uuid"),
        ("payload", "jsonb NOT NULL"),
    ]
    for name, (kind, _required) in canonical.SCHEMA[object_name].items():
        if name in ENVELOPE_COLUMNS:
            continue
        sql_type = {"uuid": "uuid", "time": "timestamptz", "int": "bigint",
                    "bool": "boolean", "ref": "text"}.get(kind, "text")
        columns.append((f"{name}_col", sql_type))
    return columns


def table_ddl(object_name: str) -> str:
    table = _table(object_name)
    body = ",\n  ".join(f"{name} {sql}" for name, sql in _columns(object_name))
    return f"""CREATE TABLE {table} (
  {body},
  CONSTRAINT {table}_tenant_id_not_null CHECK (tenant_id IS NOT NULL)
);

CREATE INDEX {table}_tenant_id_idx ON {table} (tenant_id, id);
CREATE INDEX {table}_tenant_valid_idx ON {table} (tenant_id, valid_from);

ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;

CREATE POLICY {table}_tenant_isolation ON {table}
  USING (tenant_id = current_setting('{TENANT_SETTING}')::uuid)
  WITH CHECK (tenant_id = current_setting('{TENANT_SETTING}')::uuid);"""


def _table(object_name: str) -> str:
    return "t_" + re.sub(r"(?<!^)(?=[A-Z])", "_", object_name).lower()


def schema_ddl() -> str:
    """The whole schema, in one file a migration runner can apply."""
    header = (
        "-- Generated from tessera.canonical.SCHEMA. Do not edit by hand.\n"
        f"-- Canonical schema version {canonical.SCHEMA_VERSION}.\n"
        f"-- Every table is tenant-scoped, bi-temporal and row-level secured.\n"
        f"-- Set the tenant per connection: SET {TENANT_SETTING} = '<tenant uuid>';\n\n"
        "CREATE EXTENSION IF NOT EXISTS pgcrypto;\n\n"
    )
    return header + "\n\n".join(table_ddl(name) for name in canonical.SCHEMA) + "\n"


def validate(sql: str) -> list[str]:
    """Check the DDL against the acceptance criterion. Returns problems, not a bool.

    Four things per table, and the fourth is the one people forget: FORCE ROW
    LEVEL SECURITY, without which the table owner - which is usually the
    application's own role - bypasses every policy.
    """
    problems = []
    tables = re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", sql, re.DOTALL)
    if not tables:
        return ["no CREATE TABLE statements found"]

    for table, body in tables:
        for column in ("id", "tenant_id", "valid_from", "valid_to", "tx_time"):
            if not re.search(rf"\b{column}\b", body):
                problems.append(f"{table}: missing column {column}")
        if not re.search(rf"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;", sql):
            problems.append(f"{table}: row-level security is not enabled")
        if not re.search(rf"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;", sql):
            problems.append(
                f"{table}: row-level security is not forced, so the table owner bypasses it")
        policy = re.search(rf"CREATE POLICY {table}_tenant_isolation ON {table}\s+(.*?);",
                           sql, re.DOTALL)
        if not policy:
            problems.append(f"{table}: no tenant policy")
        else:
            body_policy = policy.group(1)
            if "tenant_id" not in body_policy:
                problems.append(f"{table}: the policy does not filter on tenant_id")
            if TENANT_SETTING not in body_policy:
                problems.append(f"{table}: the policy does not read {TENANT_SETTING}")
            if "WITH CHECK" not in body_policy:
                problems.append(f"{table}: the policy has no WITH CHECK, so writes escape it")
        if not re.search(rf"CREATE INDEX {table}_tenant_id_idx ON {table} \(tenant_id, id\);", sql):
            problems.append(f"{table}: no index on (tenant_id, id)")

    expected = {_table(name) for name in canonical.SCHEMA}
    found = {table for table, _ in tables}
    for missing in sorted(expected - found):
        problems.append(f"{missing}: table is missing from the schema")
    for extra in sorted(found - expected):
        problems.append(f"{extra}: table is not a canonical object")

    return problems


# ---------------------------------------------------------------------------
# The runnable path
# ---------------------------------------------------------------------------

class StoreError(Exception):
    """Raised when a store operation breaks its contract."""


class SqliteStore:
    """The same contract as the Postgres schema, on SQLite.

    One table, one row per record, keyed by (tenant, object, id). Tenant isolation
    is a property of every statement here rather than of the engine, which is the
    difference between this and the DDL above and the reason both exist.
    """

    def __init__(self, path: str = ":memory:"):
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self._create()

    def _create(self) -> None:
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS records (
              tenant_id TEXT NOT NULL,
              object_name TEXT NOT NULL,
              id TEXT NOT NULL,
              valid_from TEXT,
              valid_to TEXT,
              tx_time TEXT NOT NULL,
              payload TEXT NOT NULL,
              PRIMARY KEY (tenant_id, object_name, id)
            )""")
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS records_tenant_object
            ON records (tenant_id, object_name)""")
        self.connection.commit()

    def put(self, tenant_id: str, object_name: str, record: dict) -> str:
        if object_name not in canonical.SCHEMA:
            raise StoreError(f"unknown object {object_name!r}")
        problems = canonical.validate(object_name, record)
        if problems:
            raise StoreError("; ".join(problems[:3]))
        if record.get("tenant_id") != tenant_id:
            raise StoreError(
                "the record's tenant does not match the session; a store that trusts "
                "the caller's tenant is a store with no isolation")
        self.connection.execute("""
            INSERT INTO records (tenant_id, object_name, id, valid_from, valid_to,
                                 tx_time, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (tenant_id, object_name, id) DO UPDATE SET
              valid_from = excluded.valid_from,
              valid_to = excluded.valid_to,
              tx_time = excluded.tx_time,
              payload = excluded.payload
            """, (tenant_id, object_name, record["id"], record.get("valid_from"),
                  record.get("valid_to"), record["tx_time"], json.dumps(record)))
        self.connection.commit()
        return record["id"]

    def get(self, tenant_id: str, object_name: str, record_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT payload FROM records WHERE tenant_id = ? AND object_name = ? AND id = ?",
            (tenant_id, object_name, record_id)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list(self, tenant_id: str, object_name: str) -> list[dict]:
        rows = self.connection.execute(
            "SELECT payload FROM records WHERE tenant_id = ? AND object_name = ? "
            "ORDER BY id", (tenant_id, object_name)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def count(self, tenant_id: str, object_name: str | None = None) -> int:
        if object_name:
            row = self.connection.execute(
                "SELECT COUNT(*) AS n FROM records WHERE tenant_id = ? AND object_name = ?",
                (tenant_id, object_name)).fetchone()
        else:
            row = self.connection.execute(
                "SELECT COUNT(*) AS n FROM records WHERE tenant_id = ?",
                (tenant_id,)).fetchone()
        return row["n"]

    def delete(self, tenant_id: str, object_name: str, record_id: str) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM records WHERE tenant_id = ? AND object_name = ? AND id = ?",
            (tenant_id, object_name, record_id))
        self.connection.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        self.connection.close()
