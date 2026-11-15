# 52 — Conformance to the original brief

**Status: Draft, 15 November 2026**

The project began as a 261-line build prompt. This document maps its twenty v1 deliverables to what exists, names every
deviation, and states what was deliberately not built. It is the closing of the loop on the brief itself — the one
document that answers "did you build what you were asked for?" rather than "does the code work?".

Read with [CLAIMS.md](../CLAIMS.md), which covers whether each claim is *true*; this covers whether each requirement was
*attempted*.

## The twenty

| # | Brief | State | Deviation, where one exists |
|---|---|---|---|
| 1 | Docker Compose + Kubernetes manifests | **Built, unrun** | Written and hardened; no Docker in the build environment, so never started |
| 2 | **Django** models for all v1 objects | **Deviated** | The canonical schema, validation, bi-temporal columns and the Postgres DDL exist; there is no Django and no ORM. The brief named a framework; the requirement was the model |
| 3 | Federation layer: schema, 4 connectors, ledger, conflict, routing | **Built** | Four connectors, 16-check suite, hash-chained ledger, five-step resolution, weighted routing |
| 4 | **SvelteKit** web + **Flutter** mobile with sync | **Deviated** | A single-file HTML app and a WebView APK. No SvelteKit, no Flutter, no SQLCipher. The local-first sync engine exists as a durable outbox; the frameworks do not |
| 5 | Workforce: seats, tasks, routing, escalation, handoff, shadow mode | **Built** | Two autonomy tiers (shadow, confirm-then-run), signed handoff packets, revocation |
| 6 | Automation: full trigger/condition/action set | **Built** | Five triggers, eleven actions, a condition language that is not Python, a proposal gate |
| 7 | Graph sidecar + RVS service | **Partial** | RVS is scored twice to 6 dp; there is no graph store |
| 8 | Git history + Markdown mirror services | **Partial** | Rebuild, revert-by-append and archival exist; no git or markdown mirror |
| 9 | Compliance substrate + three-layer security | **Built** | Object, field and row gates; consent per record; erasure is a tombstone (R-07 open) |
| 10 | Boring features + escape hatches | **Partial** | Import, undo, backup, views, reports; five of six boring features |
| 11 | Design system: 80 icons, components, dark mode, density, WCAG | **Built** | 83 icons, measured contrast both themes, density modes, a token set |
| 12 | Jargon lint that fails the build | **Built** | 13 terms, blocks release, no suppression mechanism |
| 13 | Migration wizard + keyboard translator + template gallery | **Built** | Auto-mapping, dry run, rollback, shortcuts, templates |
| 14 | Bootcamp, coach, help, glossary, docs site, changelog, **academy videos**, **email drip**, **community** | **Partial** | Documentation site, changelog, glossary and the bootcamp structure exist. **No videos, no email drip, no community platform** |
| 15 | i18n (5 languages) + multi-currency + timezone | **Partial** | Five locales and the RTL mechanism; no translated screens |
| 16 | Plugin hardening: allowlist, pinned hashes, static analysis, sandbox | **Built** | Five gates, an `ast` scan, never executes |
| 17 | Encrypted offline mobile (SQLCipher, outbox, delta sync) | **Partial** | A durable outbox and a WebView APK; **no encryption at rest on the device** |
| 18 | OpenAPI + MCP discovery (10 tools) | **Built** | OpenAPI 3.1 validates; ten tools, access-tested |
| 19 | 10-minute onboarding delivering the aha moment | **Partial** | The aha path exists and is documented; it has never been timed with a person |
| 20 | Recorded build log per batch | **Partial** | A changelog per release; no per-batch log with code, demo and decision |

**Built: 9 · Partial: 9 · Deviated: 2 · Untouched: 0.**

## The two deviations, argued

**No Django.** The brief named a framework; the requirement underneath it was a validated, tenant-scoped, bi-temporal
object model with row-level security. That exists — `canonical.py`, `store.py`, and a DDL that Postgres's own parser
accepts. Choosing Django would have added an ORM dependency to a repository whose stated constraint is the standard
library only. **The deviation is defensible and it is still a deviation: a reviewer asked for Django and did not get it.**

**No SvelteKit, no Flutter.** The brief asked for two framework applications and a sync engine. What exists is one HTML
file that runs offline, and an Android shell around it. The sync engine is real — a durable outbox with idempotent
replay — but it is not SQLCipher and it is not Flutter. **This is the largest deviation in the project**, and the honest
reason is that a framework build needs a toolchain the environment does not have; a single file does not.

## What was deliberately not built

| Not built | Why |
|---|---|
| Academy videos | No video production; the structure and scripts are not written either |
| Email drip | No mail service, no consent flow for marketing mail |
| Community platform | Nothing to put in it yet — a forum with no members is a cost, not a feature |
| Encryption at rest on mobile | Needs a key custody story the brief describes and the implementation does not have |
| Graph sidecar | The score is computed without one; a graph store would be a second source of truth |

## What the brief asked for that is better than it asked

Two places where the implementation exceeds the brief, recorded so the deviation ledger is not only negative:

- **The claim register.** The brief asked for a recorded build log. This project has something stricter: every public
  claim mapped to the command that checks it, with four marked unverified in the table.
- **Tenancy.** The brief described a single founder and one organisation. The implementation isolates tenants by
  construction, with eight tests, because the second customer arrives before the first invoice.

## The verdict

**Nine of twenty delivered whole, nine partial, two deviated, none untouched.** Every partial and every deviation is
named above with its reason. Nothing in this table is a surprise to a reader of the README, which is the standard this
document holds itself to.
