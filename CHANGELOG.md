# Changelog

Format follows Keep a Changelog. Versions follow the specification, not the (nonexistent) implementation.

## [Unreleased]

Nothing yet.

## [1.5.0] - 2026-11-14

### Added

- `tessera/ratelimit.py` - token bucket, per-node admission control with in-flight and queue caps. Backpressure
  surfaces as `RateLimited` rather than a seventh error type, because the taxonomy is closed and the caller's
  response is the same either way.
- `tessera/observability.py` - bounded histograms with nearest-rank percentiles and a target gate that treats an
  absent measurement as `unmeasured`, never as passing.
- `tessera/bench.py` - the regression harness, and a printed statement of what it is not.
- `Mesh.sync()` now admits through the node budget before every call.
- [docs/23-stage-one.md](docs/23-stage-one.md).

### Changed

- The four sync modes are enforced per field, not merely recorded. A field mirrored from every node that
  carries it now refuses the write instead of silently accepting it.
- A node that does not name a field is `bidirectional`. The source document did not state a default; this one
  does, and records the choice.
- Deliverable 3 is closed: all seven of its criteria are met.

### Fixed

- **R-05.** `Histogram.percentile()` returned 0.0 for an out-of-range argument instead of raising, and used a
  rounding formula that reported p95 of 1..100 as 96. Nearest rank now, and the argument is validated first.

## [1.4.0] - 2026-11-14

### Added

- `tessera/transport.py` - the HTTP seam, the status-to-taxonomy mapping shared by both transports, and a
  recording transport that applies the same mapping so a fixture exercises the production path.
- `tessera/providers/` - HubSpot (CRM v3), Salesforce (REST v60) and Zendesk (Support v2), each with its own
  field map, cursor shape and write envelope, behind one contract.
- An identity decision, recorded rather than assumed: the canonical id is a UUIDv5 derived from the provider id
  in a node-scoped namespace, remembered in an identity map, so a node can be replaced without rewriting
  history. Tenant policy fields are stamped by the connector, not read from the provider.
- [docs/22-providers.md](docs/22-providers.md).
- 21 more tests (169 total). All four connectors pass the same sixteen-check conformance suite.

### Caveat

The three provider connectors have never been run against a live account. Their field names, endpoints and
cursors come from public documentation and are exercised through recorded transports that speak those shapes.

## [1.3.0] - 2026-11-14

### Added

- `tessera/connector.py` - the eight-method contract, a closed error taxonomy, a per-node circuit breaker and a
  retry wrapper that distinguishes a throttle from a failure.
- `tessera/connectors.py` - `NativeConnector`, `SimulatedConnector`, and `BrokenConnector` with nine deliberate
  violations so the suite can be tested against what it must reject.
- `tessera/conformance.py` - sixteen named checks, run against a live connector. `assert_conforms()` for use in
  a connector's own tests.
- `tessera/mesh.py` - registration, sync with canonical validation at the boundary, the unified view with
  per-field provenance, write-back to the declared owner, and the activation event from
  [docs/01-product.md](docs/01-product.md).
- `python3 -m tessera.cli mesh` - the federation demonstration.
- [docs/21-connectors-and-mesh.md](docs/21-connectors-and-mesh.md).
- 53 more tests (148 total).

### Fixed

- **R-04.** The unified view reported agreeing nodes as a conflict. Two systems reporting the same value now
  resolve as `agreement` and are kept out of the conflict log, so the log contains only real disagreements.

## [1.2.0] - 2026-11-14

### Added

- `tessera/` - a dependency-free reference core: canonical schema with validation, append-only hash-chained
  ledger with verification and anchoring, every metric in the dictionary, versioned routing weights, and
  five-step conflict resolution.
- `tests/` - 95 tests, standard library `unittest`, no dependencies.
- `python3 -m tessera.cli demo` - an end-to-end demonstration including tamper detection.
- [docs/20-reference-core.md](docs/20-reference-core.md) - what is implemented, what is not, and where the
  boundary sits against the 22 acceptance criteria.
- A test job in `.github/workflows/docs.yml`.

### Fixed

- **R-01.** `data_freshness` omitted the `ln 2`, producing a 1/e life instead of a half-life, and disagreeing
  with the relationship score's decay. Both now halve at the stated half-life.
- **R-02.** The point-in-time query seeked instead of filtering, which loses late-arriving events. It now
  filters, and the module says why.
- **R-03.** Conflict resolution did not state which authority-map modes claim a field outright. Only
  `authority` does; `delegate` falls through to trust.

## [1.1.1] - 2026-11-14

### Added

- Landing page at <https://drsamonline.github.io/tessera/>: one file, no dependencies, no network calls, no
  analytics, dark and light, keyboard first.
- `docs/404.html` and `docs/.nojekyll` for GitHub Pages.
- `VERSION` file.

## [1.1.0] - 2026-11-14

### Added

- Repository created: `tessera`, the mosaic layer above every CRM.
- Full engineering specification across 21 documents, restructured from a 261-line build prompt.
- Metric dictionary defining every composite score once, with normalization, window, sample floor and version.
- History authority ruling: the event ledger is authoritative; bi-temporal columns and git checkpoints are
  derived projections.
- 22 deliverable acceptance criteria, each testable.
- Assumption register: 18 recorded assumptions closing gaps that the source document left open.
- Defect register: 43 defects with severity, location, impact and fix.
- Research notes on DPDP Rules 2025 and AI Act timing, checked against primary sources on 2026-11-14.
- Rendered deliverables: audit report (PDF), specification (DOCX), traceability matrices (XLSX).

### Changed

- Three unwritten layers (3, 4, 5) moved to a roadmap document with entry criteria instead of remaining
  unexplained rows in a layer table.
- Deployment profiles reconciled; the review queue moved from P2 to P1 because it is not an AI feature.
- 40 claimed inventions reclassified: 18 prior art, 10 partly novel, 10 speculative, 2 research-stage.
- Schedule re-baselined from 30 sprints to 44 at a stated capacity assumption (estimate, method recorded).

### Corrected

- The source document's 30-day DSAR clock is a GDPR transplant and is now a per-jurisdiction configuration.
- An earlier reading that treated the 72-hour breach clock as a GDPR transplant was wrong: DPDP Rules 2025 rule
  7(2) requires it. The breach workflow is retained unchanged.
