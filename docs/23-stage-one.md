# 23 - Stage one, complete

**Status: Draft**

Stage 1 of [15-build-sequence.md](15-build-sequence.md) is the mesh core: four connectors, the ledger, the
unified view, conflict resolution, write-back, routing, backpressure and observability. Everything in that list
now exists and is tested. This document records what closed and what the closure does and does not mean.

## What closed

| Stage 1 item | Where it lives | Evidence |
|---|---|---|
| Four connectors | `tessera/providers/`, `tessera/connectors.py` | 16/16 conformance checks, four connectors |
| Universal ledger | `tessera/ledger.py` | Chain verifies; tamper, deletion and reorder all caught |
| Unified customer view | `tessera/mesh.py` | `unified_view()` with per-field provenance |
| Conflict resolution | `tessera/conflict.py`, `tessera/mesh.py` | Five-step order, every path recorded |
| Write-back with sync modes | `tessera/mesh.py` | Four modes enforced per field |
| Routing | `tessera/routing.py` | Versioned weights, total order, term-by-term breakdown |
| Backpressure | `tessera/ratelimit.py` | Token bucket, in-flight cap, queue cap |
| Observability | `tessera/observability.py`, `tessera/bench.py` | p50/p95/p99 per operation, regression gate |

## The four sync modes, enforced

Before this, the modes existed as authority-map values that only conflict resolution read. A field declared
`mirror` could still be written by the mesh, which made the mode a comment.

| Modes across the nodes carrying a field | What a write does |
|---|---|
| Any node declares `authority` or `delegate` | That node is written, and only it |
| Every node declares `mirror` | `PermissionError`. The mesh does not write to a mirror |
| Some `mirror`, some undeclared | The mirror is skipped, the writable node takes the write |
| All `bidirectional` | The most trusted node is written, then the lowest id |

A node that does not name a field is `bidirectional`: silence is not a claim of ownership, but it is also not a
refusal to accept a write. That default is a decision, and it is recorded here because the source document did
not make it.

## Backpressure, and why it is not a new error type

Two mechanisms, deliberately separate:

- **`TokenBucket`** - the node's declared rate, refilling continuously, capped at its burst.
- **`NodeBudget`** - admission control on top: a token and an in-flight cap. A bounded queue was removed
  rather than faked: nothing in this runtime queues, so the limit could never fire (R-10, [31-code-review.md](31-code-review.md)).

Both surface as `RateLimited`, carrying the wait. Not a new exception type: the taxonomy is closed at six
([02-architecture.md](02-architecture.md#failure-semantics)), and from the caller's position a node's throttle
and our own admission control are the same event - wait, then retry. A seventh type would make every caller
learn a distinction that does not change what they do.

`Mesh.sync()` admits through the budget before every node call and releases after. A node that refuses
admission is skipped and counted, not retried in a loop.

## Measurement

Defect B-07 said there was no harness, no percentile window and no regression gate. All three now exist.

```
python3 -m tessera.bench          # measure and print
python3 -m tessera.bench --gate   # exit non-zero on a breach
```

```
operation                              n      p50      p95      p99      max
canonical.validate                   500   0.006   0.009   0.010   0.070
ledger.append                        500   0.379   1.083   2.526  26.706
routing.score                        500   0.009   0.010   0.018   0.065
metrics.trust_score                  500   0.094   0.121   0.132   0.151
mesh.unified_view                    250   0.110   0.152   0.165   0.189
ledger.verify_whole_chain              1  61.551  61.551  61.551  61.551
```

Times are milliseconds, on one process, with no network. **These are not the load-model numbers.** The targets
in [04-core.md](04-core.md) are stated for 1M records per tenant, 200 concurrent users and an 8 vCPU / 32 GB
host. A run at 500 records says nothing about that, and the program says so in its own output rather than in a
footnote.

What the harness is for is regression: the same shapes of work at a size that finishes in seconds, so a change
that makes the ledger three times slower is caught before it ships. The thresholds are separate numbers, in
`bench.REGRESSION_TARGETS`, and they are deliberately not the load-model targets.

`check_against_targets()` treats a missing or empty histogram as `unmeasured`, never as passing. A gate that
treats absence as success is not a gate.

### Why it is not in CI yet

The gate runs locally. On a shared CI runner the numbers move by an order of magnitude between machines, and a
gate that fails on a noisy neighbour gets disabled within a week. It goes into CI when the thresholds are set
from a measured baseline on a pinned runner, and not before.

## Deliverable 3, closed

| Criterion | State |
|---|---|
| Canonical schema v1 with 10 objects | Met |
| Four connectors pass one shared conformance suite | Met - native, HubSpot, Salesforce, Zendesk |
| Ledger chain recomputes | Met |
| A same-field conflict from two nodes resolves deterministically and is logged | Met |
| Routing returns a term-by-term breakdown | Met |
| Write-back with sync modes | Met |
| Backpressure and circuit breakers per node | Met |

One caveat travels with the whole row: the three provider connectors are tested against recorded transports
that speak their documented shapes, not against live tenants. The criterion is met at the level it can be met
in this repository. A live sweep against a sandbox account is the next thing that would change the evidence,
and it is recorded as such in [22-providers.md](22-providers.md).

## What Stage 1 does not include

Stage 1 was never the whole v1. Still absent, and still honest to say so:

- The native CRM core: local-first sync, optimistic mutations, list and detail views, Kanban, search.
- The workforce runtime: seats, tasks, escalation, handoff, revocation polling.
- Any interface at all. Nothing renders.
- HTTP, OpenAPI and the MCP surface.
- Postgres, row-level security, bi-temporal columns as columns rather than as ledger projections.
