# 33 - Boring features and escape hatches

**Status: Draft**

Reference: [17-constraints.md](17-constraints.md). Deliverable 10.

The specification calls these credibility markers and trust markers. It is right on both counts: nobody switches
CRM for a CSV importer, and nobody switches to one that has none.

## Five of the six boring features

| Feature | Where | Test |
|---|---|---|
| CSV import with mapping, validation and dry run | `bulk.preview`, `bulk.Importer` | `test_preview_writes_nothing`, `test_commit_imports_the_valid_rows` |
| Rollback of an import batch | `bulk.Importer.rollback` | `test_rollback_removes_the_batch` |
| Bulk operations with undo | `bulk.BulkUpdate` | `test_undo_restores_the_prior_values` |
| Point-in-time backup and restore | `bulk.Backup` | `test_restore_reproduces_the_chain`, `test_a_forged_backup_is_refused` |
| List view customisation | `views.SavedView`, `views.ViewStore` | `test_a_view_filters`, `test_a_view_sorts_and_limits` |
| Report builder | `views.Report` | `test_sum_by_group`, `test_csv_export` |
| Admin console | **Not built** | - |

### The dry run writes nothing, and validates what the commit will write

The first version of `preview()` validated a payload without the defaults the commit applies, so every row failed
with "required field missing" and the dry run reported a file that was fine as broken. A preview that validates a
different payload from the one that gets written is a preview nobody can trust; it now mints the same ids and
applies the same defaults.

### Undo does not store state

`BulkUpdate.undo(token, previous)` takes the prior values from the caller. Storing them in the tool would make it a
second source of truth for state, which is the thing the ledger exists to prevent. The token carries the
references; the caller supplies what it read.

### A restore verifies before it overwrites

`Backup.restore` checks the bundle checksum and then verifies the restored chain before returning. A restore that
trusts its input can be handed a forged backup and quietly replace a customer's history.

## All four escape hatches

| Hatch | What it does | Why it exists |
|---|---|---|
| `schema_export` | The canonical schema as JSON | A tenant that cannot see its own data model cannot leave, and a tenant that cannot leave will not arrive |
| `record_export` | Every field of every record | An admin with a legitimate reason needs the whole record; one audited door beats widening every other |
| `query` | `SELECT <fields> FROM <object> [WHERE ...] [LIMIT n]` | The question a screen cannot answer |
| `break_glass` | A time-boxed admin grant with a stated reason | The 3am incident |

Three rules hold for all four:

- **A role check runs first.** `admin`, every hatch, no exception.
- **Every use is audited**, including a refused one. `escape.denied` is a ledger event, because an attempt to
  reach a hatch is exactly the thing an incident review wants to see.
- **Nothing writes**, except break-glass, which writes only its own grant.

### The query hatch is not SQL, and says so

It is a `SELECT`-shaped grammar over the projection, with the automation condition language in the `WHERE` clause.
`DELETE`, `DROP`, `UPDATE`, and a stacked `; DROP TABLE` are all refused by the statement matcher, and the test
asserts each one by name.

Calling it raw SQL would be a lie, and shipping a real SQL engine over a dictionary would be a worse one. When the
Postgres store lands, this becomes a real read-only SQL connection and the note changes.

### Break-glass expires by clock

`grant_active(token, now)` compares against an expiry. An admin who forgets to revoke is the normal case, not the
exceptional one, so the grant does not depend on anybody remembering.

## Deliverable 10, updated

| Criterion | State |
|---|---|
| Six boring features each have a test | **Five of six** - the admin console is not built; the API covers user management and the audit viewer in part |
| Four escape hatches reachable only by an authorised role | Met - all four refuse a non-admin, asserted per hatch |
| Every use logged as a ledger event | Met - including a refused use |

## What is not here

- **No admin console.** The API has the routes an interface would call and there is no interface.
- **No real SQL.** See above.
- **No streaming import.** A CSV is read into memory. A million-row import needs a chunked reader and a progress
  cursor, and this has neither.
- **No scheduled backups.** `Backup.create()` is called by an operator. Nothing ticks.
- **No undo for an import after a restart.** Batch ids live in memory.
