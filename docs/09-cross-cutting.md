# 09 - Cross-cutting concerns

**Status: Frozen**

Three one-line bullets became three specifications, because the deliverable list promises them.
*(Closes A-05.)*

## Identity and security

OIDC and SAML SSO, MFA, session management with device binding, agent passports (time-bound, budget-bound,
human-seat-bound), break-glass admin with mandatory audit and automatic expiry.

Every control names its enforcement point and carries one test. A control without a test is not a control.

| Control | Enforcement point | Test |
|---|---|---|
| SSO | Identity provider assertion validated at the session boundary | Replay of a stale assertion is rejected |
| MFA | Second factor required before any session token is issued | Token request without a factor is refused |
| Agent passport | Signed, expiring credential checked on every agent action | An expired passport cannot act |
| Break-glass | Named role, time-boxed, every use written to the ledger | Expiry revokes access without operator action |
| Field-level security | Query execution, not controller | Denied field absent from API, export and MCP output |

## Observability and operations

p50, p95 and p99 per layer, structured logs with tenant and trace correlation, distributed traces across
connector calls, SLO-based alerting with error budgets, runbooks per alert, and an incident response process
with a post-incident review requirement.

## Governance and compliance

DSAR, consent, retention, audit chain, AI Act classification per AI action at v1, data residency per tenant and
per node. *(Closes E-02.)*

Classification is a v1 deliverable because transparency obligations are enforceable now; high-risk conformity
work is deferred to v2 because those obligations start in December 2027. See
[research/compliance.md](research/compliance.md).
