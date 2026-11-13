# 12 - AI contract

**Status: Frozen**

Non-negotiable. Each clause has a test.

| # | Clause | Test |
|---|---|---|
| 1 | Boots and passes the full test suite with zero AI containers | P0 profile run in CI with no model container present |
| 2 | No AI in the critical path: read, write, sync, auth, search, report, notification | Dependency test asserting no AI client is reachable from those paths |
| 3 | AI disabled by default; enabled per deployment, per tenant, per user | Feature flag defaults asserted at boot |
| 4 | AI writes proposals, not commits; the review queue mediates | An unapproved proposal cannot reach a node |
| 5 | No AI-only schema; embeddings in pgvector only | Schema test: no table is unreachable without a model |
| 6 | Local models first-class; external endpoints opt-in, logged, consent-gated, redactable, kill-switchable | Kill switch halts external calls within one request |
| 7 | Deterministic defaults are feature-complete without AI | The deterministic feature register runs at P0 |

## Deterministic defaults that must work with AI off

Activity capture (ICS and email headers), rule-based scoring, PostgreSQL full-text search, email templates,
activity summaries, rule-based playbooks, deterministic deduplication, threshold alerts, weighted pipeline
forecast, graph-math relationship score.

## The review queue is not an AI feature

The review queue moves to P1 because it is a deterministic approval surface. Bundling it with the MCP container
forced v1 to ship inside a profile the AI contract forbids by default. *(Closes C-05, C-07.)*

## Agent constraints

An agent occupant may not: approve its own proposal, modify consent state, modify pipeline settings, act without
a live principal, or act without a fallback seat declared on its seat.

Removing the principal halts the agent on the timeline in [05-workforce.md](05-workforce.md#revocation).
