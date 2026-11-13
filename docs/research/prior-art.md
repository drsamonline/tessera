# Prior art

**Status: Frozen**

Named systems behind the invention classifications in
[14-invention-register.md](../14-invention-register.md). A classification without a named system is an opinion;
this document makes each one checkable.

## Patterns classified as prior art

| Pattern | Where it is standard |
|---|---|
| Bi-temporal records | Snodgrass, *Temporal Databases* (1994); SQL:2011 system-versioned tables; XTDB; Datomic |
| Local-first sync | Local-first software literature (Kleppmann et al., 2019); Replicache; ElectricSQL; Automerge |
| Transactional outbox | Microservices data-consistency literature; Debezium; every mature offline-first client |
| Event sourcing and audit logs | Fowler's event-sourcing pattern; Kafka; append-only audit tables in every regulated industry |
| Row-level security | PostgreSQL RLS; Oracle VPD; the standard multi-tenant isolation mechanism |
| Capability-based routing | Capability-based scheduling literature; Kubernetes node selectors and taints |
| Escalation policies | PagerDuty, ServiceNow, Opsgenie escalation chains |
| Shadow deployment | Canary and dark-launch release practice |
| Workforce management | Shift scheduling and capacity planning, standard since the 1990s |
| App marketplaces with revenue share | Every platform marketplace since the iPhone App Store |
| Fair queuing | Nagle (1987); WFQ in network scheduling |
| Data virtualisation | Denodo, Cinchy, Dremio; federated query engines |
| Usage and outcome billing | Metering infrastructure (Stripe, Metronome, Amberflo) |
| Protocol interop | OpenAPI, MCP, A2A |

## Patterns classified as partly novel

| Pattern | What is actually new |
|---|---|
| Identity spine with per-cell provenance | A stable entity id plus provenance at the cell, not the row, plus a graph overlay keyed by the same id |
| Autonomy-aware review queue | Binding approval semantics to a seat's autonomy tier rather than to a role |
| Portable record contracts | Data portability as a signed contractual artefact with a schema-valid export guarantee |
| Seat-based versioned job descriptions | An org design object that is simultaneously RBAC, capacity and versioned contract |
| Signed full-state handoff | The signature plus the completeness requirement, not the handoff itself |
| AI proposal to deterministic compilation | The gate that turns a proposal into a workflow with no model on the execution path |
| Federated mesh with ledger and authority map | The combination, not the federation |

## Patterns that are speculative

Cross-company chains, customer-side agent bridges, universal org chart protocol, dispute trails, mesh-level
digital twins. Each needs a counterparty, a schema and an adoption path that do not exist. They are recorded as
roadmap with entry criteria and nothing more.

## How to use this

Before building anything in the partly-novel column, check whether the prior art already solves 80% of it. Before
claiming anything in the prior-art column as a differentiator, read the named system. The register exists to stop
both mistakes.
