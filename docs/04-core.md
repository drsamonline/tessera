# 04 - CRM core (Layer 1)

**Status: Frozen**

A reference implementation of the canonical schema, deployable as the only node for a solo founder.

## Objects by version

- **v1:** Contact, Company, Deal, Pipeline, Activity, Task, Ticket (basic).
- **v2:** Invoice, Contract, Product, Playbook, KnowledgeBaseEntry, Partner, Renewal, FeedbackItem.

Every entity carries `consent_state`, `lawful_basis`, `purpose_id`, `retention_policy_id` and
`data_subject_request_refs`. Purpose is an object, not a string, so purpose limitation is enforceable.
*(Closes E-04.)*

## Stack

- Django REST, PostgreSQL 16 with row-level security.
- SvelteKit web with local-first sync over OPFS SQLite, client-generated IDs, optimistic mutations and
  deterministic conflict resolution.
- Flutter mobile with SQLCipher, a transactional outbox and delta sync.
- NATS event bus at P1 and above, Kafka at scale.
- CQRS: append-only event log, materialized read models, read replicas.
- Neo4j sidecar for the relationship graph and the relationship score, built asynchronously.
- Object storage for the Markdown mirror.

## Performance

Latency targets had no load model and were therefore unmeasurable. Every target now carries one.
*(Closes B-05, B-07.)*

**Load model:** 1M records per tenant, 200 concurrent users, 25 KB median payload, 8 vCPU / 32 GB, warm cache.

| Target | Value | Notes |
|---|---|---|
| Read p95 | < 100 ms | Under the load model above |
| Write local ack p95 | < 50 ms | Local ack means the client store committed, not the server |
| Ledger append p95 | < 120 ms | Server-side, batched |
| Git checkpoint p95 | < 2 s | Every 100 events or 30 s, whichever comes first |
| Search p95 | < 250 ms | PostgreSQL full-text, 1M records, unfiltered |
| Unified view p95 | < 400 ms | Two external nodes, cold canonical cache |

The unbounded claim "no perceptible slowdown as data grows" is replaced by a scaling statement: read latency
grows with the log of tenant record count and is re-tested at 1M, 5M and 20M records per tenant. A regression
beyond 10% in any percentile fails CI. *(Closes B-06.)*

### The harness

`python3 -m tessera.bench --gate` measures the reference core and fails on a regression. It is explicit about
what it is not: it runs at a reference scale of a few thousand records on one process, which says nothing about
the load model above. The thresholds it enforces are separate regression numbers, not these targets.
[23-stage-one.md](23-stage-one.md#measurement).

## Security

Three layers, all enforced at query execution rather than in controllers:

1. **Object-level** &mdash; CRUD per object.
2. **Field-level** &mdash; read and edit per field.
3. **Row-level** &mdash; row, owner, role.

No client, API or MCP tool bypasses them. The MCP surface reuses the same enforcement path, which is the only
way the "no bypass" guarantee is true.

## Compliance

The substrate is written to DPDP as the primary regime with GDPR as a configurable second.
*(Closes E-01.)*

- **Breach:** immediate first intimation to the Data Protection Board and to affected Data Principals, detailed
  intimation within 72 hours, matching DPDP Rules 2025 rule 7. The 72-hour clock in the source document was
  correct; the 30-day DSAR clock was not. See [research/compliance.md](research/compliance.md).
- **DSAR:** access, erasure, portability, rectification. The clock is a per-jurisdiction configuration,
  default 30 days, and is not published as a statutory commitment until confirmed by counsel.
- **Consent:** notice object plus purpose object plus consent record, not a single state field.
- **Retention:** engine with legal hold. Immutable audit log with external chain anchoring
  ([11-history-authority.md](11-history-authority.md)).
- **v1 artefacts:** DPIA template, record of processing, sub-processor register, data residency option.
  *(Closes E-03.)*

## Accessibility, globalisation, offline

- **Accessibility:** WCAG 2.2 AA, keyboard-first, screen-reader tested, ARIA, text spacing, no mouse-only path.
  The manual test matrix is a deliverable, not an intention.
- **Globalisation:** multi-currency with historical rates at transaction date, per-user timezone, locale-aware
  formatting. v1 ships i18n infrastructure with EN, ES, FR, DE, PT and RTL support; 25 locales by v2 through
  community translation with a QA gate.
- **Offline:** a valid state, not an error. SQLCipher on mobile, transactional outbox, delta sync, deterministic
  conflict resolution, schema migration without data loss.
