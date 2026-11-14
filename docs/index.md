# Documentation index

> The published landing page is at <https://drsamonline.github.io/tessera/>. It links back into these
> documents on GitHub, because GitHub Pages serves this folder without a markdown renderer.

Status legend used across this repository:

| Label | Meaning |
|---|---|
| **Frozen** | Decided, tested against, not to be changed without a decision record |
| **Draft** | Written and internally consistent, awaiting review |
| **Proposed** | Written as an option, not adopted |
| **Roadmap** | Deliberately deferred; entry criteria written, no v1 obligation |

Everything below is **Frozen** unless the document says otherwise on its first line.

## Reading order

| # | Document | Layer | Why read it |
|---|---|---|---|
| 01 | [Product definition](01-product.md) | &mdash; | Customers, the activation event, what is out of scope |
| 02 | [Architecture](02-architecture.md) | all | Layer model, boundaries, failure semantics |
| 03 | [Federation mesh](03-mesh.md) | 0 | Nodes, canonical schema, connectors, routing, ledger |
| 04 | [CRM core](04-core.md) | 1 | Objects, stack, load model, security, compliance |
| 05 | [Workforce](05-workforce.md) | 2 | Seats, occupancy, handoff, escalation, revocation |
| 06 | [Roadmap layers](06-roadmap.md) | 3-5 | What is deferred and the criteria to start |
| 07 | [Experience](07-experience.md) | 6 | Design system, jargon discipline, migration |
| 08 | [Learning](08-learning.md) | 7 | The ten enablement artefacts |
| 09 | [Cross-cutting](09-cross-cutting.md) | &mdash; | Identity, observability, governance |
| 10 | [Metric dictionary](10-metrics.md) | all | The only place a score is defined |
| 11 | [History authority](11-history-authority.md) | all | Which history mechanism wins, and why |
| 12 | [AI contract](12-ai-contract.md) | all | The non-negotiables and their tests |
| 13 | [Deployment profiles](13-deployment.md) | all | P0 to P3, and what degrades where |
| 14 | [Invention register](14-invention-register.md) | all | 40 claims reclassified against prior art |
| 15 | [Build sequence](15-build-sequence.md) | &mdash; | Seven stages, exit criteria |
| 16 | [Acceptance criteria](16-acceptance-criteria.md) | &mdash; | 22 deliverables, 22 tests |
| 17 | [Constraints](17-constraints.md) | &mdash; | What must never be built |
| 18 | [Assumptions](18-assumptions.md) | &mdash; | Every gap closed by record, not by invention |
| 19 | [Open decisions](19-open-decisions.md) | &mdash; | Four items needing a founder's signature |
| 20 | [Reference core](20-reference-core.md) | 0, 1, 2 | What is actually implemented, tested, and what is not |
| 21 | [Connectors and mesh](21-connectors-and-mesh.md) | 0 | The connector contract, the conformance suite, the unified view |
| 22 | [Provider connectors](22-providers.md) | 0 | HubSpot, Salesforce and Zendesk behind a transport seam |
| 23 | [Stage one, complete](23-stage-one.md) | 0 | Sync modes, backpressure, measurement, and what closed |
| 24 | [Projections and checkpoints](24-history-projections.md) | 1 | Bi-temporal views, rebuild, revert by compensation, the mirror |
| 25 | [Deterministic features](25-deterministic-features.md) | all | What works with every model switched off, and what does not yet |
| 26 | [Workforce](26-workforce.md) | 2 | Seats, handoff packets, escalation, revocation, autonomy |
| 27 | [API and contracts](27-api-and-contracts.md) | all | The HTTP surface, OpenAPI 3.1, the 10 MCP tools |
| 28 | [Access control](28-access-control.md) | 1 | Object, field and row rules, enforced at one gate |
| 29 | [Compliance](29-compliance.md) | 1 | Consent, DSAR, retention, audit export, and R-07 |
| 30 | [Local-first sync](30-local-first-sync.md) | 1 | One protocol, offline writes, guaranteed convergence |
| 31 | [Code review](31-code-review.md) | all | 13 findings, 11 fixed, and the ship-or-block verdict |
| 32 | [Automation](32-automation.md) | 2 | Triggers, a condition language that is not Python, and the approval gate |
| 33 | [Boring features and escape hatches](33-boring-and-escape.md) | 1 | Import, undo, backup, views, reports, and four audited doors |
| 34 | [Localisation](34-localisation.md) | 6 | Five locales, RTL mechanism, historical rates, timezones |

## Audit

| Document | What it holds |
|---|---|
| [Method](audit/method.md) | How the specification was audited, and what was checked against primary sources |
| [Defect register](audit/defect-register.md) | 43 defects: severity, location, impact, fix |
| [Remediation order](audit/remediation-order.md) | Why the fixes are sequenced the way they are |

## Research

| Document | What it holds |
|---|---|
| [Prior art](research/prior-art.md) | Named systems behind the invention classifications |
| [Compliance, checked 2026](research/compliance.md) | DPDP Rules 2025 and AI Act timing, with sources |

## Rendered deliverables

The same specification as files, for circulation and review:

- [Audit report (PDF)](../deliverables/CRM_Fabric_Audit.pdf)
- [Specification (DOCX)](../deliverables/CRM_Fabric_Spec_v1.1.docx)
- [Traceability matrices (XLSX)](../deliverables/CRM_Fabric_Traceability.xlsx)

The markdown in this directory is the source of truth. If a rendered file disagrees with it, the markdown wins
and the rendered file is regenerated.
