# 31 - Code review

**Status: Draft**

An independent review of 6,474 lines across 22 modules, run on 14 November 2026. Every finding cites the file and
the failing case; a finding that could not be pointed at was dropped.

## Method

1. Intent first: the specification and the 30 documents, so the review argues with the code rather than with a
   documented decision.
2. Hunt in priority order: correctness and data loss, then security, then performance pathologies, then design.
3. Prove each finding with a failing case before fixing it. Every fix below arrived with a test that fails on the
   old code.
4. A style preference that a linter covers is not a finding, and is not in this document.

## Findings, fixed in this pass

| # | Severity | Where | What was wrong | Fix |
|---|---|---|---|---|
| **R-08** | Blocker | `ledger.knows_at`, `projection.as_of`, `projection.valid_at` | Timestamps are written at two precisions - seconds by the workforce layer, milliseconds by the ledger - and were compared as **strings**. `"…05:20:44Z"` sorts *after* `"…05:20:44.582Z"` because `Z` > `.`, so a point-in-time query could return a later state for an earlier instant | `canonical.parse_time()`; every comparison is between instants |
| **R-09** | Blocker | `checkpoint.revert_to` | A revert wrote `{"record": {}}` for a record that did not exist at the checkpoint. The projection iterates the record's fields, so an empty dict changed nothing and the record survived the revert. **A revert that silently does nothing is worse than one that fails** | An empty target writes a tombstone instead |
| **R-10** | Major | `ratelimit.NodeBudget` | `max_queue` and `queued` could never fire: nothing in the runtime queues, so the counter never rose. A limit that cannot fire is worse than no limit, because it appears in the documentation and in the operator's mental model | The field is removed, not faked. A bounded queue belongs to the caller that owns the work |
| **R-11** | Major | `api._audit` | Every caller was recorded as `"human"` - `"human" if principal.id else "system"` is always truthy - so an agent's action was indistinguishable from a person's in the audit trail. The trail is the product's central claim | `Principal.kind`, recorded as written |
| **R-12** | Major | `ledger.append` | No `fsync`. The ledger is described as *the* record, and it was the record only until the machine lost power | `EventLog(path, durable=True)` fsyncs per append; off by default so the suite stays fast, on in any deployment that claims durability |
| **R-13** | Minor | `api._authenticate` | Token lookup returned early on the first differing byte. A weak timing signal, and a token comparison is not the place to be relaxed | `hmac.compare_digest` over every token |

R-08 and R-09 are the two that mattered. Both were invisible to the test suite because every existing fixture used
one timestamp precision and never reverted to a checkpoint that predated a record.

## Findings, open

| # | Severity | Where | What is wrong | Why it is not fixed here |
|---|---|---|---|---|
| O-01 | Major | `conformance.run_conformance` | It writes test records **into the connector under test**, polluting a live node. It bit the `mesh` demonstration, which had to use fresh instances | A fix needs a read-only mode on the connector contract, which is a design change rather than a patch |
| O-02 | Major | `providers.base.write` | Idempotency is keyed on the caller's key. The same canonical record written twice with two different keys creates two external records | The provider APIs do not expose a canonical-id upsert; needs a lookup-before-create and a decision about the race |
| O-03 | Minor | `api._write_field` | A connector failure surfaces as 500, not 502 | Correct-looking but the status taxonomy is not written down anywhere to check it against |
| O-04 | Minor | `canonical.validate` | The `uuid` check accepts 36 dashes. It is a shape check, and the docstring does not say so | Documented in the review; a strict check belongs in the identity layer, not the validator |
| O-05 | Major | `ledger.verify` | O(n) with a full file re-read. 61 ms at 500 events, so minutes at a million | Incremental verification needs a checkpoint-anchored verify, which is the next projection work |
| O-06 | Major | `projection`, `compliance.export` | Rebuilds from the log on every call | Same: incremental projection with a cursor |
| O-07 | Major | `sync` | No deletion. Deleting a record is a field write today | Recorded in [30-local-first-sync.md](30-local-first-sync.md); needs tombstones in the protocol |
| O-08 | Minor | `conflict.resolve` | The `field_priority` branch returns `candidates[0]` when several tie, so the winner depends on input order | Deterministic per run, not a total order. Needs a declared priority list per field |
| O-09 | Minor | `api` | No rate limiting on authentication attempts | Belongs to the transport, and there is no transport |
| O-10 | Minor | `openapi.validate` | Does not check that every `{parameter}` in a path is declared | The real spec validator does, and it is the optional check |

## Closed since this review

| # | What was wrong | Fix | Evidence |
|---|---|---|---|
| O-05 | `ledger.verify` re-read the whole file: O(n) per call | `verify(anchor=...)` continues the chain from a checkpoint hash | `test_a_clean_log_verifies_from_an_anchor` |
| O-06 | The projection rebuilt from the log on every read | `EventLog.read_from(offset)` plus `Projection(incremental=True).refresh()` reads only the bytes that arrived | 57.6 ms rebuild against **0.6 ms** incremental at 2,000 events |
| O-01 | The conformance suite wrote test records into the node it certified | `sandbox=True` snapshots and restores a connector that supports it | `test_certifying_a_connector_does_not_pollute_it` |
| O-02 | Idempotency was keyed on the caller's key, so a restart created a duplicate | `identity_path` persists the canonical-to-external map | `test_the_identity_survives_a_restart` |
| O-07 | No deletion in the sync protocol | A reserved `__deleted__` field, so the merge rule needs no special case | `test_deletion_converges`, `test_deletion_reaches_the_ledger_and_the_projection` |
| R-12 | Durability was opt-in | It is now the default; a deployment has to opt out | `test_durability_is_on_by_default` |

An anchored verify cannot see a rewrite **before** its own anchor, and the test asserts that limitation rather
than hiding it: `test_tampering_before_the_anchor_is_not_caught_and_that_is_the_trade`. That is why the anchor
must come from somewhere the database owner does not control - the external anchor in
[11-history-authority.md](11-history-authority.md) - and why a full verify is still the weekly job.

## Verdict

**Code gate: pass. Product gate: blocked on scope, not on quality.** All five unblock conditions from this
review are closed. What remains is not a defect list - it is twelve deliverables that were never started.

| Gate | Result | Why |
|---|---|---|
| Correctness and data loss | Pass after R-08, R-09 | Both fixed, both with regression tests |
| Security | Pass for the stated scope | Constant-time tokens, loopback-only server, no eval/exec/pickle/subprocess anywhere in the tree, no secrets in the source |
| Performance | Fail at scale | `verify` and `projection` are O(n) per call; the benchmark says so at 500 records and the load model is 1M |
| Documentation coverage | Pass | 31 documents, every module has a docstring naming the decision it implements |
| Test coverage of the claims | Pass | 387 tests; every guarantee in the README has a named test |

### Unblock conditions, all closed

| # | Condition | State |
|---|---|---|
| 1 | Incremental verification and projection (O-05, O-06) | Closed - 0.6 ms against 57.6 ms |
| 2 | The suite must not write to the node it certifies (O-01) | Closed - sandbox by default |
| 3 | A retry must not duplicate an external record (O-02) | Closed - durable identity map |
| 4 | Deletion (O-07) | Closed - reserved tombstone field, explicit resurrection |
| 5 | Durability defaults to safe (R-12) | Closed - opt out, not opt in |

What is left is not quality. It is scope: twelve deliverables never started, no interface, no Postgres, no
container.

## What the review says about the process

Six of the eight modules reviewed had at least one finding, and the two blockers were both in code that the test
suite exercised heavily. The suite tested the happy path of every module and the **boundaries between modules**
were where the defects lived: two precisions of timestamp meeting in a comparison, a projection meeting a revert.

That is the argument for a review pass over a green test suite, and it is why this document exists rather than a
note that the tests pass.
