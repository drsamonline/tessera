# 39 - Postgres, row-level security, and what could not be run

**Status: Draft**

Reference: [04-core.md](04-core.md#stack). Deliverable 2.

## What exists

| Artefact | What it does |
|---|---|
| `store.schema_ddl()` | Generates the Postgres DDL for all ten canonical objects from `canonical.SCHEMA` |
| `store.validate()` | Reads the DDL back and asserts the four things the criterion asks for, per table |
| `store.SqliteStore` | The same contract, runnable, with tenant isolation on every statement |

Every table carries `id`, `tenant_id`, `valid_from`, `valid_to`, `tx_time`, `created_at`, `updated_at`,
`owner_seat_id` and a `jsonb` payload, plus indexes on `(tenant_id, id)` and `(tenant_id, valid_from)`.

## The four assertions

`store.validate()` returns a list of problems, and `test_the_schema_is_structurally_sound` asserts it is empty:

| Assertion | Why it matters |
|---|---|
| Bi-temporal columns on every table | The product's central query is "what was true, and what did we know" |
| `ENABLE ROW LEVEL SECURITY` | Without it, a policy exists and does nothing |
| `FORCE ROW LEVEL SECURITY` | Without it, the **table owner** bypasses every policy - and the owner is usually the application's own role. This is the one people forget, so it has its own test |
| `CREATE POLICY ... USING ... WITH CHECK` | `USING` filters reads; only `WITH CHECK` constrains writes. A policy with `USING` alone lets a tenant write a row into another tenant |

`test_every_policy_reads_the_session_tenant` asserts `current_setting('tessera.tenant_id')` appears exactly twice per
table - once in `USING`, once in `WITH CHECK` - which is the count that would go wrong if somebody "simplified" a
policy.

## What could not be run, and why

**The DDL has never been executed.** This environment ships the Postgres *client* (`psql` 15) and not the server:
`initdb`, `pg_ctl` and `postgres` are absent from `/usr/lib/postgresql/15/bin`. The DDL was generated and read back,
not applied.

**There are no Django models.** Django is not installed and the reference core has no dependencies; writing models
that cannot be imported would put untested code in the tree. The DDL is what a Django model would produce, and the
store contract is what a Django app would bind to.

Both of those are stated as gaps rather than as work.

## The runnable path is SQLite, and it is not a substitute

`SqliteStore` exists so the store's behaviour is tested rather than described. It is one table keyed by
`(tenant_id, object_name, id)`, and **tenant isolation is a property of every statement** rather than of the engine.

That difference is the whole argument for the Postgres schema. SQLite has no row-level security, so isolation here
depends on nobody ever writing a query without the tenant predicate. In Postgres it depends on a policy the engine
enforces. The SQLite store proves the contract; the DDL is what makes the contract safe.

Three tests are worth naming:

- `test_a_record_is_invisible_to_another_tenant` - the same record id, a different tenant, nothing returned.
- `test_two_tenants_hold_the_same_id_without_colliding` - the composite key does its job.
- `test_a_record_whose_tenant_does_not_match_the_session_is_refused` - a store that trusts the caller's tenant is a
  store with no isolation.

## Deliverable 2, updated

| Criterion | State |
|---|---|
| Django models for the v1 objects | **Not met** - no Django, by design |
| A migration applies to an empty Postgres 16 | **Unverified** - no server available to apply it to |
| Every tenant-scoped table has RLS enabled, asserted by a schema test | Met - `validate()`, ten tables |
| Bi-temporal columns on every entity | Met - asserted per table |

## What it would take to close the first two

1. Add Django and a Postgres server to CI, and run `schema_ddl()` as a migration against an empty database.
2. Replace the generated DDL with Django migrations once the models exist, keeping `validate()` as the gate - the
   assertion does not care which tool produced the SQL.
3. Point `SqliteStore`'s callers at a Postgres store and delete the SQLite path, or keep it as the test double.

## Update, 15 November 2026: the syntax is now a fact

The DDL is parsed by **libpg_query** — the parser the Postgres server itself uses — through `pglast`.

```
$ python3 scripts/validate_ddl.py
pglast v8.8 · 61 statements · 10 tables · 10 policies
OK — every statement parses as valid Postgres syntax
Not proven: that it runs. Constraints, extensions and privileges are resolved by
the server, not the parser.
```

That closes half of the gap and leaves the other half open on purpose.

| Question | Answered by | Status |
|---|---|---|
| Is it valid Postgres syntax? | `pglast`, the server's own parser | **Yes, proven** |
| Does it have the properties we promised? | `store.validate()`, regex-based | Yes, proven |
| Does it run against a real server? | A server | **No. Still never executed** |

The test that matters here is `test_the_parser_rejects_a_broken_statement`: a check that cannot fail is not a check,
and a validator that has never rejected anything is a validator nobody should trust.

What the parser cannot see: whether `pgcrypto` is available, whether the role in `SET tessera.tenant_id` exists,
whether `FORCE ROW LEVEL SECURITY` behaves as expected against a table owner, and whether the policies permit what
they claim to permit. Those need a server.
