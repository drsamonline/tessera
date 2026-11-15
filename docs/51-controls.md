# 51 — IT general controls, and how they are tested

**Status: Draft, 15 November 2026. Not audit or legal advice.**

TESSERA is not a financial reporting system, so SOX 404 does not bite it directly. What bites is the question a buyer's
auditor asks anyway: **what are your IT general controls, and how do you know they operated?**

This document maps each control to the code that implements it, the test that evidences it, and — where there is no
test — says so. The method is the one used for ICFR testing: state the control objective, separate design from
operating effectiveness, test with evidence that stands alone, and classify what is missing rather than rounding it up.

## Scope, and why these six

The population is every control in the reference implementation that a customer's auditor would rely on. Six survive
that filter; the rest are engineering hygiene that no one relies on for a conclusion.

| # | Control objective | The risk it addresses |
|---|---|---|
| C-1 | Every change to a record is recorded, attributable and ordered | A change happens and nobody can say who made it, when, or what it replaced |
| C-2 | The record of changes cannot be altered without detection | Someone with database access rewrites history |
| C-3 | Access to a field is limited by role, not by endpoint | A read scope grants the whole record |
| C-4 | One tenant's data is unreachable from another's session | A missing filter becomes a breach |
| C-5 | A deletion is attributable and explained | Records vanish with no reason on file |
| C-6 | A change is not lost when the process dies | A write is acknowledged and then dropped |

## C-1 — Every change is recorded, attributable and ordered

| | |
|---|---|
| **Implementation** | `tessera/ledger.py::EventLog.append` — one event per action, monotonic sequence, actor vocabulary restricted to `human` / `agent` / `system` |
| **Design effectiveness** | **Effective.** The append is the only path to a state change; the projection is derived from the log, not written directly |
| **Operating effectiveness** | Tested: `tests/test_ledger.py`, `tests/test_standalone.py::TestTombstone` |
| **Evidence** | A `record.created` event carrying the principal in its payload; sequence numbers contiguous on replay |
| **Gap** | The actor vocabulary has three values. A principal id travels in the payload, so "which human" depends on the caller being honest about it |

## C-2 — The record cannot be altered without detection

| | |
|---|---|
| **Implementation** | SHA-256 chaining in `EventLog.append`; `EventLog.verify` recomputes the chain; `tessera/anchor.py` writes periodic anchors |
| **Design effectiveness** | **Effective for the chain as stored.** Tampering with any event breaks every hash after it |
| **Operating effectiveness** | Tested: verification over a rewritten file, and the console's Tamper control reproduces it in the browser |
| **Evidence** | `python3 -m tessera.cli verify` returns the first bad sequence number |
| **Gap** | **Anchoring is not scheduled.** An attacker who rewrites the whole file and recomputes every hash produces a valid chain; only an anchor held elsewhere detects that. The code exists; the schedule does not |

## C-3 — Access is limited by role, not by endpoint

| | |
|---|---|
| **Implementation** | `tessera/access.py` — `can_read_field`, `can_edit_field`, `redact`, `filter_rows`; the API checks scope **and** the policy checks role |
| **Design effectiveness** | **Effective.** Two independent gates, and the field class comes from the canonical schema rather than from the caller |
| **Operating effectiveness** | Tested: `tests/test_access.py`, and the API tests assert a read scope does not grant an edit |
| **Evidence** | A redacted record returned to a lower role, with the denied field names listed rather than silently omitted |
| **Gap** | No test asserts that **every** route goes through the policy. A new route added without the check would pass the suite |

## C-4 — One tenant's data is unreachable from another's session

| | |
|---|---|
| **Implementation** | `tessera/tenants.py::TenantRouter` — one `Mesh`, one `EventLog`, one `Projection` per tenant |
| **Design effectiveness** | **Effective by construction.** There is no shared table to filter, so there is no predicate to forget |
| **Operating effectiveness** | Tested: `tests/test_tenants.py`, eight tests including a cross-tenant read by id returning `404` |
| **Evidence** | Two tenants, separate record sets, no shared ids, a create in one invisible in the other |
| **Gap** | Isolation is per process. A deployment that runs one process per tenant inherits none of this and needs the Postgres RLS path — which has never been executed |

## C-5 — A deletion is attributable and explained

| | |
|---|---|
| **Implementation** | `Mesh.tombstone` — requires a reason, appends `record.tombstoned`, the projection stops serving the record |
| **Design effectiveness** | **Effective for attribution.** Not effective for erasure — see below |
| **Operating effectiveness** | Tested: `tests/test_standalone.py::TestTombstone`, six tests including `reason_required` and `409` on a second delete |
| **Evidence** | A `record.tombstoned` event with the reason in its payload; a read returning `404`; the ledger still holding the record |
| **Gap** | **Design deficiency, accepted and documented (R-07).** The bytes are not destroyed. Under the DPDP Act, "we stopped serving it and recorded why" is a defensible position and not the same as erasure. Crypto-shredding is the correct answer and needs a dependency the engine does not have |

## C-6 — A change is not lost when the process dies

| | |
|---|---|
| **Implementation** | The console's durable outbox (`state.outbox`, IndexedDB) and the engine's append-then-derive order |
| **Design effectiveness** | **Effective on the client.** The engine appends to a file with `durable=True`; there is no fsync-per-event option, so a power loss can lose the last event |
| **Operating effectiveness** | Partially tested: the outbox replays idempotently; a killed process was not simulated |
| **Evidence** | Intents survive a reload; ids make replay idempotent |
| **Gap** | **No test kills the process mid-write.** That is the test this control actually needs and it does not exist |

## Deficiency classification

Using the standard criteria — likelihood of misstatement and magnitude, aggregated by objective.

| Finding | Classification | Why |
|---|---|---|
| Anchoring not scheduled (C-2) | **Deficiency** | A determined attacker with file access is undetected. No compensating control, because the anchor exists but is never taken |
| No route-completeness test (C-3) | **Deficiency** | The control is effective today; the *test of the control* has a hole. A future route could bypass it silently |
| Erasure not cryptographic (C-5) | **Significant deficiency** for a DPDP-relevant deployment | A data principal's erasure request cannot be fully honoured. The position is documented, not fixed |
| No crash test (C-6) | **Deficiency** | The control's operating effectiveness is asserted rather than evidenced |
| RLS never executed (C-4, in a per-tenant deployment) | **Significant deficiency** in that deployment model | The isolation claim rests on SQL that has never run |

Aggregated: C-4 and C-5 both bear on *data integrity and confidentiality in a deployed environment*, and both are
unverified in the same direction — the code is written, the execution is not. That aggregation is the honest finding of
this document.

## What this document is not

- **Not an opinion on materiality.** That depends on the customer's financials, which do not exist yet.
- **Not an attestation.** No auditor has reviewed it. A qualified professional signs the conclusion.
- **Not complete.** It covers six controls chosen because an auditor would rely on them. It does not cover change
  management, vendor management, backup and recovery, or physical security, because none of them exists yet.
