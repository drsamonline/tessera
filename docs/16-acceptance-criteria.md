# 16 - Acceptance criteria

**Status: Frozen**

Twenty-two deliverables, twenty-two testable criteria. This table is what an acceptance report reports
against. *(Closes G-01.)*

A batch is complete when its deliverables' criteria pass, not when its code compiles. The build log
records the criterion id, the test that proves it, and the run.

| No | Deliverable | Stage | Acceptance criterion |
|---|---|---|---|
| 1 | Docker Compose + Kubernetes manifests | 0 | Compose reaches healthy P0 state in under 5 minutes on a clean host; full suite green at P0; no P0 service references S3, Neo4j, NATS, Redis or any AI container. |
| 2 | Django models for all v1 objects | 0 | Migration applies to empty Postgres 16; every tenant-scoped table has RLS enabled, asserted by schema test; bi-temporal columns present on every entity. |
| 3 | Federation layer | 1 | Canonical schema v1 with 10 objects; 4 connectors pass one shared conformance suite; ledger chain recomputes; a same-field conflict from two nodes resolves deterministically and is logged; routing returns a term-by-term breakdown. |
| 4 | Local-first web + mobile sync engine | 2 | Client renders with the server stopped; offline write reconciles with no lost update; 1,000 concurrent mutations produce zero divergence; one protocol serves online and offline. |
| 5 | Workforce layer | 3 | Task routes by documented score with logged breakdown; agent seat rejected without fallback_seat_id; escalation rejected without HandoffPacket; receiver reconstructs full state from the packet alone. |
| 6 | Automation framework | 3 | All 5 triggers and 11 actions covered by tests; AI-authored workflow stored as proposal and non-executable until approved; dependency test asserts no AI call on the execution path. |
| 7 | Graph sidecar + RVS service | 2 | RVS computed from the published formula; two independent implementations agree to 6 decimal places on one fixture; service optional at P0 and its absence does not fail the P0 suite. |
| 8 | Git history + Markdown mirror | 2 | Any record's full write history reconstructable; revert restores prior state and is itself logged; mirror lag exposed as a metric; mirror failure does not fail a write. |
| 9 | Compliance substrate + 3-layer security | 5 | FLS-denied field absent from API response, export and MCP output in three separate tests; RLS violation returns zero rows; DSAR export complete within configured SLA; chain verifies over 1M events. |
| 10 | Boring features + escape hatches | 5 | Six boring features each have a test; four escape hatches reachable only by authorised role and every use logged as a UniversalEvent. |
| 11 | Design system (80 icons, components, dark, density, WCAG) | 4 | 80 icons present; every component renders in light, dark and both densities; contrast recorded per component; WCAG 2.2 AA manual test matrix complete and attached. |
| 12 | Jargon lint rule | 4 | Rule runs in CI; a fixture introducing each of the 13 jargon terms fails the build; zero leaks in the shipped string catalogue. |
| 13 | Migration wizard + keyboard translator + template gallery | 4 | Dry run against HubSpot, Salesforce and Zendesk maps at least 90% of fields automatically, lists the remainder, and rollback restores pre-migration state exactly. |
| 14 | Learning artefacts | 4 | Four role bootcamps each reach the defined activation event; 5 videos and the sandbox linked from the in-app coach; every glossary term maps to a UI string key. |
| 15 | i18n (5 locales) + multi-currency + timezone | 5 | Five locales render without truncation on the 12 highest-traffic screens; RTL verified on 3 screens; historical-rate conversion matches the recorded rate on transaction date. |
| 16 | Plugin hardening | 5 | Unsigned plugin rejected; modified hash rejected; out-of-allowlist network call blocked and logged. |
| 17 | Encrypted offline mobile | 2 | SQLCipher key absent from plaintext disk; outbox survives app kill; delta sync after 7 days offline loses no data. |
| 18 | OpenAPI + MCP discovery schema (10 tools) | 0 | OpenAPI validates against 3.1; all 10 tools carry schema, auth scope and audit emission; every tool passes the FLS and RLS tests from deliverable 9. |
| 19 | 10-minute onboarding flow | 4 | Activation event fires in a scripted first-run test; time-to-activation measured on 10 external users and reported, not asserted. |
| 20 | Recorded build log | 6 | One entry per batch with code ref, tests, demo link, docs diff, decision IDs, acceptance report against this table, and risk update. |
| 21 | v2/v3/v4 roadmap | 6 | Every deferred invention has an entry criterion, a dependency and a success metric. |
| 22 | Cross-cutting specifications | 6 | Identity/Security, Observability and Governance each have a written spec with named enforcement points and one test per control. |

## Criteria that are easy to fake

Four criteria are passable with a screenshot and a confident sentence. Each has a mechanical check instead:

| Deliverable | Mechanical check |
|---|---|
| 7 - Relationship score | Two independent implementations agree to six decimal places on one fixture |
| 9 - Access enforcement | A denied field is asserted absent from API, export and MCP output, in three tests |
| 12 - Jargon lint | A fixture introducing each of the 13 terms fails the build |
| 19 - Onboarding | Time-to-activation measured on 10 external users and reported |

## Where the criteria came from

Each criterion answers the question the original build prompt never asked: what would a reviewer see
that proves this exists and works. Where a criterion needed a number the specification did not supply,
the number is in [10-metrics.md](10-metrics.md) and the gap is recorded in
[18-assumptions.md](18-assumptions.md).
