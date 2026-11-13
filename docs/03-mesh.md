# 03 - Federation mesh (Layer 0)

**Status: Frozen**

Any CRM becomes a node. The mesh provides the unified view, deterministic routing and the universal ledger. No
migration is required to adopt it.

## Objects

**CRMNode** carries: `id`, `tenant_id`, `name`, `type` (native, external, partner, customer, distributor),
`category` (marketing, sales, support, billing, erp, custom), `org_id`, `capability_manifest`, `connector_id`,
`schema_map` (versioned), `authority_map` (per field: mirror, bidirectional, authority, delegate), `trust_score`,
`cost_model`, `rate_limit`, `latency_budget`, `privacy_boundary`, `status` (online, degraded, offline,
buffering).

**UniversalEvent** carries: `id`, `tenant_id`, `actor` (human, agent, system), `source_node_id`, `canonical_ref`,
`action`, `payload_hash`, `evidence_refs`, `timestamp`, `sequence`, `prev_event_hash`. Append-only and
hash-chained. It is the single authority for history; see
[11-history-authority.md](11-history-authority.md). *(Closes C-03.)*

## Canonical schema

Contact, Company, Deal, Activity, Ticket, Invoice, Task, Seat, Event, Document. Versioned. Every connector
declares which version it speaks; a version bump requires a migration path and a conformance re-run before any
connector is upgraded. Custom fields are namespaced per tenant.

The schema is versioned before the second connector is built, not after. *(Closes G-03.)*

## Connector interface

```
capabilities() schema() read() write() subscribe() health() rateLimit() costEstimate()
```

Plus the error taxonomy in [02-architecture.md](02-architecture.md#failure-semantics). Four connectors ship in
v1: HubSpot, Salesforce, Zendesk and native.

Four sync modes per field:

| Mode | Meaning |
|---|---|
| `mirror` | Read-only from the node. The mesh never writes back |
| `bidirectional` | Both sides may write; conflicts resolve by the declared order |
| `authority` | The node is the source of truth for that field |
| `delegate` | The mesh writes and the node accepts |

Every write carries an idempotency key. Retry uses backoff with jitter. Each node has a circuit breaker and a
backpressure budget.

## Routing

Routing was a bare sum of seven incommensurable terms. It is now a weighted sum over normalized terms, with a
versioned weight vector recorded on every decision. *(Closes B-01, B-04.)*

```
score = 0.30 * capability_match
      + 0.15 * authority_match
      + 0.15 * sla_headroom
      + 0.15 * trust_score
      + 0.10 * utilization
      + 0.10 * cost_efficiency
      + 0.05 * data_freshness
      - 0.20 * cross_boundary_penalty
```

Every term is normalized to `[0,1]` by the transform in [10-metrics.md](10-metrics.md). Ties break on
`trust_score`, then on lower estimated cost, then on node id for total determinism.

v1 strategies are capability-based, ownership-based and least-loaded. All three use the same scoring function
with different weight vectors, so a strategy change is a weight change and nothing else.

## Conflict resolution

Order: `authority_map`, then `trust_score`, then bi-temporal recency, then field priority, then human review.

Every conflict is written to the ledger as a `UniversalEvent` with both candidate values and the rule that
resolved it. No silent overwrites. A conflict that reaches human review blocks the field, not the record.

## Federation security

- Node attestation at connect time and on every health check.
- Per-field privacy declared in the canonical schema and enforced at the canonical layer, not in connectors.
- Connector sandboxing with an egress allowlist.
- Input validation at the canonical boundary.
- Rate limiting per node.
- Anomaly detection on write volume and on authority-map violations.
