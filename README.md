<div align="center">

<h1>TESSERA</h1>

<p><b>The mosaic layer above every CRM.</b><br>
Every system you already run becomes a tile. The tiles keep their own shape.<br>
Together they make one picture &mdash; and one tamper-evident record of how the picture was made.</p>

<p>
<a href="https://drsamonline.github.io/tessera/"><img alt="Landing page: live" src="https://img.shields.io/badge/landing%20page-live-d9a441"></a>
<img alt="Status: specification + reference core" src="https://img.shields.io/badge/status-spec%20%2B%20reference%20core-1F3552">
<img alt="Tests: 148 passing" src="https://img.shields.io/badge/tests-354%20passing-2e7d32">
<img alt="Version 1.1" src="https://img.shields.io/badge/version-1.1-2e7d32">
<img alt="Defects: 43 found, 43 closed" src="https://img.shields.io/badge/audit-43%20defects%20closed-b45309">
<img alt="License: PolyForm Noncommercial 1.0.0" src="https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-2e7d32">
</p>

<p>
<a href="https://drsamonline.github.io/tessera/"><b>Landing page</b></a> &nbsp;&middot;&nbsp;
<a href="docs/index.md"><b>Documentation</b></a> &nbsp;&middot;&nbsp;
<a href="docs/audit/defect-register.md">Audit register</a> &nbsp;&middot;&nbsp;
<a href="docs/16-acceptance-criteria.md">Acceptance criteria</a> &nbsp;&middot;&nbsp;
<a href="docs/10-metrics.md">Metric dictionary</a> &nbsp;&middot;&nbsp;
<a href="docs/19-open-decisions.md">Open decisions</a> &nbsp;&middot;&nbsp;
<a href="https://drsamonline.github.io/">All projects</a>
</p>

<p><sub>PolyForm Noncommercial 1.0.0 &copy; 2026 Dr. Sohil Momin</sub></p>

</div>

---

> **Project status: specification, plus a reference core. The product does not exist.**
> This repository is the engineering specification for TESSERA, restructured and audited on 14 November 2026.
> Every claim in these documents is a requirement, not a feature. Nothing here runs.
> The specification began as a 261-line build prompt; it was audited against itself, 43 defects were found,
> and all 43 are closed here by formal definition or by a numbered assumption
> ([defect register](docs/audit/defect-register.md), [assumptions](docs/18-assumptions.md)).
> **Nothing in this repository is measured.** Where a figure is an estimate it says so on the line it appears.
>
> What does run: `tessera/`, a dependency-free reference implementation of the canonical schema, the ledger,
> the metrics, routing, conflict resolution, the connector contract, the conformance suite, four connectors and
> a working mesh, projections that rebuild from the ledger, the workforce layer, and an HTTP surface with an OpenAPI 3.1
> contract, ten MCP tools, three-layer access control and a compliance substrate. 354 tests, standard library
> only, no network.
> [What it does and does not do](docs/20-reference-core.md).

---

## What this is

Most companies run four to seven systems that each hold a slice of the same customer. The slices disagree.
Reconciling them costs a person a morning a week, and the reconciliation is invisible to everyone else.

TESSERA is the layer that sits above those systems instead of replacing them. Each connected system becomes a
node. The mesh presents one customer view across all of them, routes work to whichever node or person should
handle it, and writes every action in every system to a single hash-chained ledger. A native CRM is one node
in that mesh, not the product. Adoption is additive: the first result arrives before anything is migrated.

The design constraint that shapes everything else: one founder and a five-thousand-person organisation run the
same code paths. That bounds the architecture, not the customer list.

## Why the name

A *tessera* was a single tile in a Roman mosaic, and separately a token of identity carried by a citizen to
prove standing. Both meanings are load-bearing here. Each connected system is a tile that keeps its own shape
and its own identity; the mesh is what makes them a picture; and the ledger is the proof of standing &mdash;
what each system knew, when it knew it, and who acted on it.

The name is deliberately outside the textile family already used elsewhere in this fleet. TESSERA is a mosaic,
not a loom.

## The three rules that do not bend

1. **No AI in the critical path.** Read, write, sync, auth, search, report and notification work with every
   AI container switched off. The full test suite must pass at the bare profile.
2. **Nothing is silently overwritten.** A cross-system conflict resolves by a declared order and is written to
   the ledger with both candidate values and the rule that settled it.
3. **History has one authority.** The event ledger is the record. Everything else &mdash; bi-temporal columns,
   git checkpoints, graph projections &mdash; is derived and must be rebuildable from it.

Each rule has a test named in [the AI contract](docs/12-ai-contract.md) and
[the history ruling](docs/11-history-authority.md). A rule without a test is a slogan.

## The eight layers

| Layer | Name | v1 | What it does |
|---|---|---|---|
| 0 | Federation mesh | Yes | Nodes, canonical schema, connectors, routing, ledger, conflict resolution |
| 1 | CRM core | Yes, optional | Reference implementation of the canonical schema |
| 2 | Workforce | v1 subset | Seats, occupants, tasks, handoff, escalation, autonomy |
| 3 | Intelligence | v2 | Graduated autonomy, workforce analytics, cost-aware routing |
| 4 | Protocol and settlement | v3 | Cross-company chains, agent-to-agent transactions |
| 5 | Economic engine | v3 | Marketplace, outcome billing, revenue share |
| 6 | Experience | Yes | Design system, jargon discipline, migration as UX |
| 7 | Learning | Yes | Bootcamp, coach, academy, docs, changelog, community |
| &mdash; | Cross-cutting | Yes | Identity, observability, governance |

Layers 3 to 5 are roadmap with written entry criteria, not placeholders. The v1 specification covers the other
five plus cross-cutting concerns. [Why the split](docs/06-roadmap.md).

## What is in this repository

| Path | What it holds |
|---|---|
| [docs/index.md](docs/index.md) | Reading order, status legend, full map |
| [docs/01-product.md](docs/01-product.md) | Product definition, customers, activation event |
| [docs/02-architecture.md](docs/02-architecture.md) | Layer model, boundaries, failure semantics |
| [docs/03-mesh.md](docs/03-mesh.md) | Layer 0 in full: objects, connectors, routing, conflicts |
| [docs/10-metrics.md](docs/10-metrics.md) | Every score in the product, defined once |
| [docs/11-history-authority.md](docs/11-history-authority.md) | Which history mechanism is authoritative |
| [docs/12-ai-contract.md](docs/12-ai-contract.md) | The non-negotiables, each with its test |
| [docs/16-acceptance-criteria.md](docs/16-acceptance-criteria.md) | 22 deliverables, 22 testable criteria |
| [docs/audit/defect-register.md](docs/audit/defect-register.md) | 43 defects with impact and fix |
| [docs/20-reference-core.md](docs/20-reference-core.md) | What is implemented, tested, and what is not |
| [docs/21-connectors-and-mesh.md](docs/21-connectors-and-mesh.md) | The connector contract, the conformance suite, the unified view |
| `tessera/` | The reference core: schema, ledger, metrics, routing, conflict, connectors, mesh |
| [docs/22-providers.md](docs/22-providers.md) | HubSpot, Salesforce and Zendesk behind a transport seam |
| [docs/23-stage-one.md](docs/23-stage-one.md) | Sync modes, backpressure, the measurement harness |
| [docs/24-history-projections.md](docs/24-history-projections.md) | Bi-temporal views, checkpoints, the mirror |
| [docs/26-workforce.md](docs/26-workforce.md) | Seats, signed handoff, escalation, revocation |
| [docs/27-api-and-contracts.md](docs/27-api-and-contracts.md) | The HTTP surface, OpenAPI 3.1, the 10 MCP tools |
| [docs/28-access-control.md](docs/28-access-control.md) | Object, field and row rules at one gate |
| [docs/29-compliance.md](docs/29-compliance.md) | Consent, DSAR, retention, audit export - and R-07 |
| `tests/` | 354 tests, standard library `unittest`, no dependencies |
| [deliverables/](deliverables) | The same specification as PDF, DOCX and XLSX |

## Run it

```bash
python3 -m tessera.cli demo                  # two systems, one contact, one ledger, tamper detection
python3 -m tessera.cli mesh                  # three nodes, one picture, the activation event
python3 -m tessera.cli workforce             # seats, a signed handoff, revocation
python3 -m tessera.cli schema                # print and check both contracts
python3 -m tessera.cli timeline              # what we knew vs what was true, then revert and mirror
python3 -m tessera.bench --gate              # measure, and fail on a regression
python3 -m unittest discover -s tests -t .   # 354 tests
```

`demo` appends two writes from two systems, asks what each system knew at two different times, resolves the
conflict between them, routes the next write, computes the trust and relationship scores, verifies the chain,
then alters one byte and verifies again.

`mesh` registers three nodes, runs the conformance suite against each connector, syncs their records, prints
the unified view with provenance on every field, shows the one real disagreement with both values, evaluates
the activation event, writes a field back to the node that owns it, and verifies the chain.

No dependencies. Python 3.10 or later. Nothing reaches the network.

## Read this in ten minutes

1. [docs/01-product.md](docs/01-product.md) &mdash; who it is for and what the first result is.
2. [docs/02-architecture.md](docs/02-architecture.md) &mdash; the layer model and the boundaries between layers.
3. [docs/11-history-authority.md](docs/11-history-authority.md) &mdash; the one ruling that makes the rest coherent.
4. [docs/12-ai-contract.md](docs/12-ai-contract.md) &mdash; what the product refuses to do.
5. [docs/19-open-decisions.md](docs/19-open-decisions.md) &mdash; what is still open and needs a decision.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) first. This is a specification repository: documentation accuracy is
the product quality. A statement that contradicts verified reality is a defect, and it is reported the same way
a code bug is.

## Licence

PolyForm Noncommercial 1.0.0 ([LICENSE](LICENSE)) &mdash; source-available, not OSI-approved open source.
Commercial use needs a separate licence. Privacy: [PRIVACY.md](PRIVACY.md). Security: [SECURITY.md](SECURITY.md).
