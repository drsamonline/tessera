# 20 - Reference core

**Status: Draft**

A dependency-free Python implementation of the five parts of the specification that are defined precisely
enough to be implemented and tested. It is not the product. It is the proof that the definitions in
[10-metrics.md](10-metrics.md) and [11-history-authority.md](11-history-authority.md) can be written down
without ambiguity.

## What exists

| Module | Lines | What it implements | Specification |
|---|---|---|---|
| `tessera/canonical.py` | 250 | UUIDv7 identity, the versioned canonical schema for 10 objects, validation, canonical hashing | [03-mesh.md](03-mesh.md#canonical-schema) |
| `tessera/ledger.py` | 230 | Append-only hash-chained event log, per-tenant sequences, verification, anchoring, point-in-time query | [11-history-authority.md](11-history-authority.md) |
| `tessera/metrics.py` | 240 | Every routing term, `trust_score`, relationship velocity score (twice), forecast | [10-metrics.md](10-metrics.md) |
| `tessera/routing.py` | 210 | Weighted routing with versioned weight vectors, deterministic tie-break, occupant selection, SLA clock | [03-mesh.md](03-mesh.md#routing), [05-workforce.md](05-workforce.md#routing) |
| `tessera/conflict.py` | 150 | Five-step conflict resolution producing a record, never a bare value | [03-mesh.md](03-mesh.md#conflict-resolution) |
| `tessera/connector.py` | 230 | The connector contract, closed error taxonomy, circuit breaker, retry wrapper | [02-architecture.md](02-architecture.md#failure-semantics) |
| `tessera/connectors.py` | 220 | Native and simulated connectors, plus a deliberately broken one | &mdash; |
| `tessera/conformance.py` | 260 | Sixteen checks that a connector must pass, tested against nine deliberate violations | [16-acceptance-criteria.md](16-acceptance-criteria.md) |
| `tessera/mesh.py` | 260 | Registration, sync, unified view, write-back, activation event | [03-mesh.md](03-mesh.md) |
| `tessera/transport.py` | 130 | The HTTP seam, the status-to-taxonomy mapping, a recording transport for tests | &mdash; |
| `tessera/providers/` | 470 | HubSpot, Salesforce and Zendesk connectors over the seam | [22-providers.md](22-providers.md) |
| `tessera/ratelimit.py` | 150 | Token bucket, per-node admission control, backpressure as `RateLimited` | [17-constraints.md](17-constraints.md), rule 15 |
| `tessera/observability.py` | 130 | Bounded histograms, nearest-rank percentiles, a target gate | [04-core.md](04-core.md#performance) |
| `tessera/bench.py` | 170 | The regression harness, and an honest statement of what it is not | &mdash; |
| `tessera/projection.py` | 190 | Current and bi-temporal state, rebuildability as a test | [11-history-authority.md](11-history-authority.md) |
| `tessera/checkpoint.py` | 170 | Chained snapshots, diff, revert by compensation | [11-history-authority.md](11-history-authority.md) |
| `tessera/mirror.py` | 160 | Markdown projection, manifest of hashes, lag as a count | [25-deterministic-features.md](25-deterministic-features.md) |
| `tessera/workforce.py` | 480 | Seats, occupants, tasks, signed handoff, escalation, revocation | [05-workforce.md](05-workforce.md) |
| `tessera/access.py` | 200 | Object, field and row rules; the one gate every read path calls | [28-access-control.md](28-access-control.md) |
| `tessera/compliance.py` | 400 | Consent, DSAR, retention, signed audit export, erasure | [29-compliance.md](29-compliance.md) |
| `tessera/sync.py` | 230 | Local-first replica, outbox, cursor, field-level LWW, convergence | [30-local-first-sync.md](30-local-first-sync.md) |
| `tessera/automation.py` | 380 | Triggers, a parsed condition language, eleven actions, the proposal gate | [32-automation.md](32-automation.md) |
| `tessera/bulk.py` | 230 | CSV import with dry run and rollback, bulk undo, backup and restore | [33-boring-and-escape.md](33-boring-and-escape.md) |
| `tessera/views.py` | 170 | Saved views and the report builder, on the same filter grammar | [33-boring-and-escape.md](33-boring-and-escape.md) |
| `tessera/escape.py` | 190 | Four escape hatches, role-gated and audited | [33-boring-and-escape.md](33-boring-and-escape.md) |
| `tessera/locale.py` | 340 | Five locales, the formatter, the RTL mirror, historical rates | [34-localisation.md](34-localisation.md) |
| `tessera/jargon.py` | 110 | The lint that blocks a release on an internal term | [35-jargon-and-plugins.md](35-jargon-and-plugins.md) |
| `tessera/plugins.py` | 210 | Allowlist, pinned hash, signature, static scan, permissions | [35-jargon-and-plugins.md](35-jargon-and-plugins.md) |
| `tessera/migrate.py` | 300 | Auto-mapping, transform, rollback, shortcut translator, template gallery | [36-migration.md](36-migration.md) |
| `tessera/api.py` | 380 | The HTTP surface: routing, bearer auth, scopes, redaction, audit | [27-api-and-contracts.md](27-api-and-contracts.md) |
| `tessera/openapi.py` | 400 | The generated OpenAPI 3.1 document and its two validators | [27-api-and-contracts.md](27-api-and-contracts.md) |
| `tessera/mcp.py` | 280 | Ten tools, each with a schema, a scope and an audit action | [27-api-and-contracts.md](27-api-and-contracts.md) |
| `tessera/cli.py` | 700 | Five demonstrations that exercise all of the above end to end | &mdash; |

No dependencies. Standard library only. No network calls. No model, no service, no container.

```bash
python3 -m tessera.cli demo          # the end-to-end demonstration
python3 -m unittest discover -s tests -t .   # 95 tests
```

## What it proves

The audit's central complaint was that seven composite scores had no formula two engineers would implement
identically. They now do. Specifically:

- **The ledger is the single authority and it verifies.** A tampered byte is caught by two independent checks
  (the event hash and the payload hash). A deleted event is caught by the sequence gap and the broken link. A
  reordered pair is caught by both.
- **The point-in-time query is answerable.** `knows_at(tenant, ref, at)` returns the last value each source node
  had written at or before a horizon, which is the product's central question, answered from one structure.
- **The relationship score is reproducible.** Two mechanically different implementations agree to six decimal
  places on a fixture. That was the acceptance criterion for deliverable 7; the criterion is now met even
  though the deliverable is not.
- **Routing is total and order-independent.** Given the same candidates and the same weight vector, the order
  does not depend on input order, and every decision carries its term-by-term breakdown and the weight version
  that produced it.
- **No conflict resolves silently.** Every path returns a record naming the rule that settled it, with both
  candidates attached, including the path that blocks.

## What it does not do

- No live provider integration. HubSpot, Salesforce and Zendesk connectors exist and pass the conformance
  suite, but only against recorded transports speaking documented shapes. No tenant, no token, no real traffic.
- No production gateway, no MCP transport. The HTTP surface, the OpenAPI document and the ten tool
  definitions exist: [27-api-and-contracts.md](27-api-and-contracts.md).
- No web or mobile client. The local-first sync protocol exists and is tested:
  [30-local-first-sync.md](30-local-first-sync.md).
- No workforce scheduler, queue persistence or capacity model. The seat, handoff, escalation and
  revocation rules are implemented: [26-workforce.md](26-workforce.md).
- No push subscription, no backpressure accounting, no interface for a blocked field.
- No database. The ledger is a JSON Lines file; Postgres with row-level security is the production target and
  is not implemented.
- No database-level access control. Object, field and row rules are enforced in Python on every read path
  ([28-access-control.md](28-access-control.md)); Postgres RLS is specified and absent.

## Three defects found by implementing the specification

Writing the code found three things reading it did not. This is the argument for a reference core existing at
all: a definition that survives an implementation is a definition, and one that does not was a description.

| # | Found in | What was wrong | Fix |
|---|---|---|---|
| R-01 | [10-metrics.md](10-metrics.md) | `data_freshness` was written as `exp(-age / half_life)`, which does not halve at the half-life &mdash; it gives 0.368, a 1/e life. The relationship score's decay, two paragraphs away, does halve. Two metrics, two meanings for the same words. | The exponent carries ln 2. At one half-life the score is 0.5, and the two decay functions now agree. |
| R-02 | [11-history-authority.md](11-history-authority.md) | The point-in-time query was implemented as a seek that stops at the first event past the horizon. That is only correct if the log is ordered by event time. It is ordered by append, and a late-arriving event may carry an earlier timestamp. | The query filters rather than seeks. A production deployment adds a time index; the reference implementation says why it does not need one at this scale. |
| R-03 | [03-mesh.md](03-mesh.md#conflict-resolution) | The authority map lists four modes and the resolution order treats "authority map" as one step, without saying which modes claim a field outright. Reading `delegate` as ownership produced a resolution where a node that only accepts mesh writes beat the node that owns the field. | Only `authority` claims a field outright. `delegate` ranks above `bidirectional` but falls through to the trust comparison. The rule is now written in the module and tested. |

Each is closed in this repository. None changes a product decision; all three change a definition that a
builder would otherwise have had to guess.

## Where this sits against the 22 deliverables

Zero of 22 deliverables are fully met. Four are partly met, and the part that is met is stated precisely.

| Deliverable | Status | What is done | What is missing |
|---|---|---|---|
| 2 - Models for v1 objects | Partial | The canonical schema for 10 objects with validation and hashing | Django models, migrations, row-level security, bi-temporal columns |
| 3 - Federation layer | Partial | Canonical schema, ledger, conflict resolution, routing, the connector contract, the conformance suite, four connectors, mesh sync, the unified view, write-back to the declared owner | Live provider integration, push subscription, backpressure, per-field sync modes |
| 7 - Graph sidecar and RVS | Partial | The score, implemented twice, agreeing to six decimals | The graph, the sidecar, the service |
| 9 - Compliance substrate | Partial | Access control, consent, DSAR, retention, audit export | Real erasure (R-07), breach workflow, ROPA, residency |

The remaining 18 are untouched. The [acceptance criteria](16-acceptance-criteria.md) are unchanged by this
document: a partial implementation does not move a criterion, it moves the evidence toward one.

## Why this is in the repository rather than a branch

Because the specification's credibility rests on it. A document that says "deterministic routing" and never
computes a route is a hope. The same document with a tested router, a verifying ledger and two agreeing score
implementations is a specification.

The boundary is stated in the README, on the landing page and in this document, because the failure mode here
is a reader assuming the product exists.
