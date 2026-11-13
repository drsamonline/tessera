# 07 - Experience (Layer 6)

**Status: Frozen**

Every screen is legible without a glossary. Internal names never reach the interface, and a lint rule enforces
it.

## Principles

Jargon-free, familiarity-preserving, progressive disclosure, opinionated defaults, no spinners, designed empty
states, keyboard-first, motion that explains causality, accessibility baked in, beautiful by default.

"No spinners" is a rule about perceived latency, not a prohibition on waiting. Where a read cannot be served
from the local replica &mdash; a federated read across an external node, a report over the full mesh &mdash; the
surface renders a skeleton with the known-stale data and a freshness marker. A blank screen is the failure; a
spinner is a symptom. *(Closes H-01.)*

## Jargon map

Enforced by lint. The build fails if any internal term reaches a user-facing string.

| Internal | Interface |
|---|---|
| CRMNode | Connected system |
| Chain | Workflow chain |
| UniversalEvent | Activity / Action |
| Canonical schema | Unified data model |
| Federation mesh | Workspace |
| Seat | Position |
| Occupant | Member |
| HandoffPacket | Context brief |
| EscalationLadder | Handoff rules |
| Autonomy tier | Trust level |
| Shadow mode | Training mode |
| Relationship Velocity Score | Relationship health |
| Forecast Provenance Ledger | How this was calculated |
| Bi-temporal records | History |

Architecture terms &mdash; CQRS, graph sidecar, object/field/row-level security &mdash; never appear in the
interface at all.

## Preserve and reinvent

**Preserve:** Kanban pipeline, contact and company detail with tabs, activity stream, list with filter and saved
views, global search, dashboard widgets, email integration, mobile, bulk actions, report builder, familiar
settings.

**Reinvent:** the one-screen customer view across every system, unified ranked search with provenance, the
what-happened timeline, the how-was-this-calculated evidence tree, who-is-working-on-this across humans and
agents, always-visible next action, zero spinners, designed empty states.

## Design system

Semantic colour tokens, modular type scale at a 1.25 ratio with a maximum of five weights, 4 px and 8 px
spacing, 80 icons in v1 and 200 by v2, a complete component library (buttons, inputs, cards, tables, modals,
toasts, tabs, dropdowns, tooltips, empty states, skeletons), motion tokens at 150 ms ease-out, dark mode on
system plus toggle, density modes, focus rings, ARIA, and recorded contrast ratios per component.

## Migration as experience

A migration wizard for HubSpot, Salesforce and Zendesk with field mapping, validation, dry run and rollback. A
keyboard shortcut translator for each source system. A template gallery with one-click pipeline, seat and org
design installation. A "keep using your old tool" mode where the mesh connects and works in the background.
