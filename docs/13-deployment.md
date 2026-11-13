# 13 - Deployment profiles

**Status: Frozen**

One codebase, four profiles. Every v1 feature has a profile that runs it, or a stated degradation.
*(Closes C-01, C-06.)*

| Feature | P0 Bare | P1 Standard | P2 Assisted | P3 Governed |
|---|---|---|---|---|
| Postgres + app + web | Yes | Yes | Yes | Yes |
| NATS event bus | No &mdash; CQRS log in Postgres | Yes | Yes | Yes |
| Read replica, Redis | No | Yes | Yes | Yes |
| Neo4j sidecar, relationship score | No &mdash; returns null, flagged in the interface | Yes | Yes | Yes |
| Object storage, Markdown mirror | No &mdash; mirror off, no failure | Optional | Yes | Yes |
| Review queue | Yes &mdash; not an AI feature | Yes | Yes | Yes |
| MCP container, 10 tools | No | No | Yes | Yes |
| Local model | No | No | Optional | Optional |
| Agent passports, autonomy tiers | No | No | No | Yes |
| Flutter / SQLCipher mobile | Client only, syncs to any profile | Yes | Yes | Yes |
| i18n, 5 locales, RTL | Yes | Yes | Yes | Yes |
| External audit anchoring | Yes &mdash; required by the immutability claim | Yes | Yes | Yes |

## The P0 gate

P0 remains the gate: the full test suite must pass with zero AI containers and no optional infrastructure. The
suite is profile-aware, and a feature that degrades at P0 must have a stated behaviour rather than an unhandled
absence.

## Why P0 matters commercially

P0 is the profile a suspicious buyer runs on a laptop before a call. If it does not pass its own suite, the
architecture claim is marketing.
