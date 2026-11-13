# 18 - Assumptions register

**Status: Draft (awaiting signature)**

Every gap closed by a recorded assumption rather than an invented requirement.
*(Closes A-02.)*

The source document forbade clarifying questions while leaving roughly twelve mechanisms undefined. That
combination forces a builder to invent design decisions invisibly. The rule is now: proceed, record the
assumption here with the next free id, and stop only at an irreversible or security-irreversible fork.

| ID | Assumption | Resolves | Sign-off |
|---|---|---|---|
| AS-01 | Primary ICP is the 3-10 person B2B agency. Solo founder is secondary. The 5,000-employee organisation is a design constraint, not a customer. | F-01, F-02 | Founder |
| AS-02 | Layers 3, 4 and 5 are roadmap. The v1 specification covers Layers 0, 1, 2, 6, 7 and cross-cutting concerns. | A-01 | Founder |
| AS-03 | Clarifying questions are permitted only at irreversible or security-irreversible forks. Every other gap is recorded as a numbered assumption in the build log and work continues. | A-02 | Founder |
| AS-04 | v1 workforce subset is Seat, Occupant, Task, HandoffPacket, EscalationLadder. Shift scheduling, cost-aware routing and workforce analytics are v2. | A-03 | Founder |
| AS-05 | UniversalEvent ledger is the single authority for history. Bi-temporal columns are a projection of it. Git history is a per-tenant commit log of ledger checkpoints, not per-write commits. | C-02, C-03 | Architecture |
| AS-06 | v1 routing weights: capability 0.30, authority 0.15, sla_headroom 0.15, trust 0.15, utilization 0.10, cost_efficiency 0.10, freshness 0.05; cross-boundary penalty 0.20. Versioned and logged per decision. | B-01, B-04 | Architecture |
| AS-07 | trust_score = clamped EWMA of success, non-escalation, non-conflict and audit-completeness rates over 90 days, minimum sample 20, prior 0.5. | B-02 | Architecture |
| AS-08 | RVS uses the formula in section 10 with a 21-day decay half-life and tenant-p95 normalization. | B-03 | Architecture |
| AS-09 | Load model for every latency target: 1M records per tenant, 200 concurrent users, 25 KB median payload, 8 vCPU / 32 GB, warm cache. | B-05 | Engineering |
| AS-10 | P0 degradation: RVS returns last-known or null; mirror and graph are absent; the review queue is present because it is not an AI feature. | C-01 | Architecture |
| AS-11 | Review queue moves to P1. MCP container and local models remain P2. | C-05, C-07 | Architecture |
| AS-12 | v1 autonomy tiers are observably distinct: shadow_only computes, logs and discards the action; confirm_then_run holds the action for approval and executes on approval. | D-01 | Product |
| AS-13 | Revocation is a signed event, polled every 5 seconds, with in-flight actions aborting at the next checkpoint and failing closed. | D-02 | Security |
| AS-14 | DSAR SLA is configurable per jurisdiction, default 30 days, and is not published as a statutory claim until confirmed by counsel. | E-01 | Legal |
| AS-15 | AI Act classification per AI action is a v1 deliverable. High-risk conformity assessment is deferred to v2. | E-02 | Legal |
| AS-16 | Ledger appends per write; git checkpoints every 100 events or 30 seconds. Commit latency is budgeted separately from write ack. | C-02 | Architecture |
| AS-17 | Chain head is published to an external append-only log every 15 minutes, with a public verification procedure. | C-04 | Security |
| AS-18 | Sprint baseline assumes 6 engineers, 1 designer, 0.5 SRE. On that basis 30 sprints re-baseline to 44 (estimate: 22 deliverables at 2 sprints each, less parallelisable overlap). | G-02 | Founder |

## How to add one

1. Take the next free `AS-NN` id.
2. State the assumption as a decision, not as a question.
3. Name the defect it resolves, or write `new` and open one in the
   [defect register](audit/defect-register.md).
4. Name who must sign it off.

An assumption without an owner is a rumour.
