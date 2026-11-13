# Changelog

Format follows Keep a Changelog. Versions follow the specification, not the (nonexistent) implementation.

## [Unreleased]

Nothing yet.

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
