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
