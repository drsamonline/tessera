# Changelog

Format follows Keep a Changelog. Versions follow the specification, not the (nonexistent) implementation.

## [Unreleased]

Nothing yet.

## [1.22.0] - 2026-11-14

### Added

- `tessera/store.py` - the Postgres DDL for all ten canonical objects, generated from the canonical schema, with
  bi-temporal columns, `ENABLE` and `FORCE ROW LEVEL SECURITY`, and a tenant policy carrying both `USING` and
  `WITH CHECK`.
- `store.validate()` - reads the DDL back and asserts those four properties per table.
- `store.SqliteStore` - the same contract, runnable, with tenant isolation on every statement.
- [docs/39-postgres.md](docs/39-postgres.md).
- 20 more tests (630 total).

### Not done, and stated as such

- **No Django models.** Django is not installed and the core has no dependencies; models that cannot be imported
  would be untested code.
- **The DDL has never been executed.** This environment ships the Postgres client and not the server - `initdb`,
  `pg_ctl` and `postgres` are absent. The DDL is generated and read back, not applied.

### Note

`FORCE ROW LEVEL SECURITY` has its own test because without it the table owner - usually the application's own role -
bypasses every policy. A policy with `USING` and no `WITH CHECK` has its own test too: `USING` filters reads and
only `WITH CHECK` constrains writes.

## [1.21.0] - 2026-11-14

### Added

- **Deliverable 1.** `Dockerfile` (python:3.12-slim, non-root uid 10001, a healthcheck that makes a real request),
  `docker-compose.yml` (read-only root, `cap_drop: ALL`, no new privileges) and `deploy/k8s.yaml` (namespace,
  config, secret, deployment, service, with probes and a hardened security context).
- `python3 -m tessera.api` - the container's entry point, with `TESSERA_HOST`, `TESSERA_PORT` and `TESSERA_TOKEN`
  from the environment and no default token in the image.
- `scripts/check_docs.py` - the gate behind the rule that every push updates the documentation and the landing
  page. It is wired into CI and into the pre-finish checklist in AGENTS.md.
- [docs/38-deployment.md](docs/38-deployment.md).
- 13 more tests (610 total), seven of which make real HTTP requests against a live socket.

### Changed

- `serve()` was split so `handler_for(api)` returns the handler class. A server testable only through its own
  process is a server nobody tests.

### Fixed

- `VERSION` said 1.1.0 while the changelog was at 1.20.0, and the landing page's document count had been wrong
  since the previous push. The new gate found both on its first run.

## [1.20.0] - 2026-11-14

### Added

- `tessera/learning.py` - deliverable 14 and the structure of 19. Four role bootcamps that each end at the
  activation event, five academy videos and a sandbox all linked from the coach, a thirteen-term glossary, the
  day 0/3/7/30 drip, and a persona changelog.
- [docs/37-learning.md](docs/37-learning.md).
- 23 more tests (597 total).

### Fixed

- The message catalogue carried ten of the thirteen interface vocabulary terms. `Activity`, `Unified data model`,
  `Workflow chain` and `History` had no `term.*` key, so the product could not say four of the words it uses. The
  glossary cross-check caught it; all four now exist in five locales and the jargon lint stayed clean.

## [1.19.0] - 2026-11-14

### Added

- `tessera/migrate.py` - deliverable 13. Auto-mapping from a source export's headers, a transform that joins
  composites and scales money to minor units, a dry run, a rollback, a keyboard shortcut translator and a template
  gallery.
- [docs/36-migration.md](docs/36-migration.md).
- 26 more tests (574 total).

### Fixed

- **R-15.** `Migration.commit()` cached the mapping from the first file it prepared, so a second migration on the
  same object silently reused the wrong headers and imported nothing. It re-derives the map from the file it is
  given.
- The wizard no longer auto-maps a source `Owner` column to `owner_seat_id`. A source owner is a name or a foreign
  identifier, not a canonical seat uuid, and the guess produced a column that failed validation on every row.

### Coverage

Field coverage on all three source exports is 100%; the unmapped source columns are listed rather than hidden, and
provider identifiers are reported separately as source ids.

## [1.18.0] - 2026-11-14

### Added

- `tessera/jargon.py` - deliverable 12. Thirteen internal terms, the map taken verbatim from the experience
  document and compared against it by a test, and a CI step that fails the build.
- `tessera/plugins.py` - deliverable 16. Allowlist, pinned hash, signature, an `ast`-based static scan and a
  permission grant. Every refusal is a ledger event.
- [docs/35-jargon-and-plugins.md](docs/35-jargon-and-plugins.md).
- 23 more tests (548 total).

### Note

The linter has no suppression mechanism, on purpose: a suppression mechanism is how a lint rule becomes a
formality.

The plugin loader never executes a plugin. A loader that runs untrusted code to find out whether it is safe to run
has already answered the question wrongly, and the test asserts that validation leaves no file behind.

## [1.17.0] - 2026-11-14

### Added

- `tessera/locale.py` - deliverable 15. A message catalogue of 28 keys in five locales with the jargon map as the
  interface vocabulary, a declared length budget per key, locale-aware number, currency, date and time formatting
  with a per-user timezone, an RTL direction flag and token mirror, and a rate table that converts on the
  transaction date.
- [docs/34-localisation.md](docs/34-localisation.md).
- 31 more tests (525 total).

### Fixed

- **R-14.** `mirror()` compared token names against lowercase literals, so `paddingLeft` and `paddingRight` failed
  every check and were copied through unchanged. An RTL layout that silently stayed LTR is the exact failure the
  function exists to prevent; its own test caught it on the first run.

### Honest boundary

The rendering half of the criterion - "five locales render without truncation on twelve screens" - cannot run
without screens. The length-budget check is what runs instead, and the doc says it is a proxy. No RTL language
ships in v1; the mechanism does.

## [1.16.0] - 2026-11-14

### Added

- `tessera/bulk.py` - CSV import with a mapping, a dry run and a rollback that tombstones the batch; bulk update
  with undo; point-in-time backup and a restore that verifies before it overwrites.
- `tessera/views.py` - saved list views and a report builder, both on the automation filter grammar rather than a
  second one.
- `tessera/escape.py` - four escape hatches: schema export, record export, a `SELECT`-shaped query, and
  break-glass with a clock-driven expiry.
- [docs/33-boring-and-escape.md](docs/33-boring-and-escape.md).
- 41 more tests (494 total).

### Fixed

- The CSV dry run validated a payload without the defaults the commit applies, so a valid file reported as broken.
  A preview that validates a different payload from the one that gets written is a preview nobody can trust.

### Note

The query hatch is not SQL and the doc says so: it is a `SELECT`-shaped grammar over the projection with the
condition language in the `WHERE`. `DELETE`, `DROP`, `UPDATE` and a stacked statement are each refused by name.

Every escape-hatch use is a ledger event, including a refused one.

## [1.15.0] - 2026-11-14

### Added

- `tessera/automation.py` - deliverable 6. Five triggers, a condition language with a tokenizer and a
  recursive-descent parser, eleven actions, and the approval gate.
- [docs/32-automation.md](docs/32-automation.md).
- 40 more tests (453 total).

### The gate

A `Proposal` cannot be registered with the engine at all: `Engine.register` refuses anything that is not a
compiled `Workflow`, so an AI-authored playbook has no path to execution that does not pass through a named human
approval. An author may not approve its own proposal, and a condition that does not parse fails at compile time
rather than at 3am.

### The condition language is not Python

A condition is data written by a customer or by a model on their behalf. It is tokenized and parsed against a
fixed grammar - no `eval`, no call syntax, no statement syntax, dunder identifiers refused, depth bounded at 24.
A missing field raises rather than evaluating false, because a condition that silently passes on a misspelled
field name is a workflow that quietly stopped working.

## [1.14.0] - 2026-11-14

### Fixed

The last three production blockers from the review, and the durability default.

- **O-01.** The conformance suite wrote test records into the node it certified. It now snapshots and restores a
  connector that supports `sandbox()`; a remote connector is certified against a sandbox tenant.
- **O-02.** Idempotency was keyed on the caller's key, so a restart forgot which external record belonged to which
  canonical id and the next write created a duplicate. `identity_path` persists the map.
- **O-07.** No deletion in the sync protocol. A reserved `__deleted__` field makes a tombstone merge like any other
  write. Resurrection is explicit, not a side effect of writing a field.
- **R-12.** Durability now defaults to on. A deployment has to opt out, which is the right way round.

### Added

- 13 more tests (413 total).

### Note

All five unblock conditions from the review are closed. What remains is scope, not quality: twelve deliverables
never started, no interface, no Postgres, no container.

## [1.13.0] - 2026-11-14

### Fixed

- **O-06.** The projection rebuilt from the log on every read. `EventLog.read_from(offset)` plus
  `Projection(incremental=True).refresh()` reads only the bytes that arrived. At 2,000 events: **57.6 ms rebuild
  against 0.6 ms incremental**.
- **O-05.** `ledger.verify` re-read the whole file. `verify(anchor=...)` continues the chain from a checkpoint
  hash, which is what makes an hourly verification job possible at a million events.

### Added

- 13 more tests (400 total), including the one that asserts what an anchored verify **cannot** catch: a rewrite
  before its own anchor. That limitation is the trade, and the external anchor is what closes it.

### Note

`build()` still replays from the start and the rebuildability test still uses it. A projection that is only ever
incremental is a projection nobody has checked.

## [1.12.0] - 2026-11-14

### Fixed

A code review over 6,474 lines found 13 findings. Six are fixed here, each with a regression test that fails on
the old code.

- **R-08 (blocker).** Point-in-time queries compared ISO timestamps as strings. Two precisions are in use - seconds
  by the workforce layer, milliseconds by the ledger - and `"…44Z"` sorts after `"…44.582Z"`. A query could return
  a later state for an earlier instant. All comparisons now go through `canonical.parse_time`.
- **R-09 (blocker).** `revert_to` wrote `{"record": {}}` for a record that did not exist at the checkpoint, which
  the projection applied as a no-op. A revert that silently does nothing is worse than one that fails. It writes a
  tombstone now.
- **R-10.** `NodeBudget.max_queue` could never fire because nothing queues. The field is removed rather than faked.
- **R-11.** Every API caller was recorded as `"human"` in the audit trail, including agents.
- **R-12.** No `fsync`. The ledger is described as the record and was the record only until the machine lost power.
  `EventLog(path, durable=True)`.
- **R-13.** Token comparison returned early on the first differing byte. `hmac.compare_digest` now.

### Added

- [docs/31-code-review.md](docs/31-code-review.md) - the findings, the seven that remain open, and the verdict.
- 14 more tests (387 total).

### Verdict

Ship as a reference implementation. Block for production until O-05 and O-06 (incremental verify and projection),
O-01, O-02 and O-07 are closed.

## [1.11.0] - 2026-11-14

### Added

- `tessera/sync.py` - the local-first protocol: a replica that writes locally and immediately, an outbox, a
  cursor, and field-level last-writer-wins over a Lamport counter with a replica-id tiebreak.
- Every accepted operation is written to the ledger, so the sync stream and the audit trail cannot disagree.
- [docs/30-local-first-sync.md](docs/30-local-first-sync.md).
- 19 more tests (373 total), including a thousand mutations across three replicas converging to one state, and
  the same operations applied forward, reversed and shuffled producing one fingerprint.

### Note

The losing write in a conflict is outranked, not deleted: both values stay in the operation log. The replica
state holds one value because an interface has to render something; the mesh's conflict resolver is where a
human decides.

There is no deletion in the sync protocol yet. Deleting a record is a field write today, which is wrong.

## [1.10.0] - 2026-11-14

### Added

- `tessera/compliance.py` - purpose-bound consent, a DSAR lifecycle with a configurable clock and a complete
  hashed export, a retention engine with legal hold, a signed audit export, and erasure by tombstone.
- `Projection` honours tombstones: an erased or expired record leaves the projection on rebuild.
- [docs/29-compliance.md](docs/29-compliance.md).
- 34 more tests (354 total).

### Fixed

- **R-07, and it is not fixed.** The ledger cannot honour an erasure request: an append-only hash chain cannot
  delete bytes already written. `erase()` tombstones, and the original payload stays in the log. Closing it needs
  crypto-shredding or segmented retention, and this repository has neither. Recorded as a defect, not a gap.

### Changed

- `DsarService` rebuilds the projection on every export instead of trusting the snapshot it was constructed with.
  An export that serves the state from before an erasure is a confident, signed, wrong answer.

## [1.9.0] - 2026-11-14

### Added

- `tessera/access.py` - object, field and row rules, enforced at one gate that every read path calls: the API,
  the export, the history, the point-in-time view, the unified view and every MCP tool.
- An export route, redacted by the same gate. An export that forgets the policy is the classic leak: the screen
  hides a column and the CSV does not.
- [docs/28-access-control.md](docs/28-access-control.md).
- 20 more tests (320 total), six of them asserting a denied field is absent from six different surfaces.

### Changed

- `owner_seat_id` moved from `Contact` into the shared canonical envelope. Row-level access control needs it on
  every object, and a rule that only works for contacts is not a rule.
- A principal with no declared role is an auditor: reads every row, edits nothing. A default of `admin` would be
  convenient and wrong.
- A rep reading a record it does not own gets 404, not 403. A 403 confirms the record exists.

### Note

Deliverable 18 is now fully met: the MCP tools pass the field and row access tests because they dispatch through
the same gate as everything else.

## [1.8.0] - 2026-11-14

### Added

- `tessera/api.py` - a stdlib HTTP surface: ten routes, bearer auth with four scopes, and an audit event naming
  the caller on every mutation. Loopback-only server included.
- `tessera/openapi.py` - the OpenAPI 3.1 document generated from the route table, with 23 schemas built from the
  canonical schema. Two validators: a structural one that always runs, and the real spec validator when it is
  installed.
- `tessera/mcp.py` - ten tools, each with a JSON Schema, an auth scope and an audit action, plus a dispatcher
  that writes a `mcp.call` event for every call including a failed one.
- `python3 -m tessera.cli schema` - print and check both contracts.
- [docs/27-api-and-contracts.md](docs/27-api-and-contracts.md).
- 41 more tests (300 total).

### Changed

- The audit event records `arguments_hash`, not the arguments. A log holding what was asked for is a second copy
  of the data with weaker access control.

### Note

The server binds to loopback. A development surface that silently listens on 0.0.0.0 is how a prototype ends up
on the internet with a bearer token in a shell history.

## [1.7.0] - 2026-11-14

### Added

- `tessera/workforce.py` - deliverable 5. Seats as versioned job descriptions, occupants as interchangeable
  humans and agents, routing with a logged breakdown, escalation ladders with two terminal states, HMAC-signed
  handoff packets carrying full state, and fail-closed revocation.
- `python3 -m tessera.cli workforce` - the demonstration, including the receiver rebuilding a task from the
  packet after the task, seat and occupant tables have been destroyed.
- [docs/26-workforce.md](docs/26-workforce.md).
- 37 more tests (259 total).

### Changed

- The two autonomy tiers are observably distinct: `shadow_only` discards the action, `confirm_then_run` holds
  it. In v1.0 of the specification both routed to the review queue and the field was decoration.
- A seat may not appear in its own escalation ladder, and may not be its own fallback. Both were loops the
  original specification permitted.

### Note

There is no default signing key. A default key is not a signature, it is decoration.

## [1.6.0] - 2026-11-14

### Added

- `tessera/projection.py` - current state and both point-in-time views (transaction time and valid time) from one
  pass over the ledger, with `verify_rebuildable()` enforcing the history ruling.
- `tessera/checkpoint.py` - chained snapshots, diff between checkpoints, and revert by compensation: a revert
  appends, it never deletes.
- `tessera/mirror.py` - the Markdown projection with a manifest of hashes and lag expressed as a count of events.
- `python3 -m tessera.cli timeline` - the demonstration, including the divergence between what was known and
  what was true.
- [docs/24-history-projections.md](docs/24-history-projections.md).
- 22 more tests (222 total).

### Fixed

- **R-06.** `Mesh.sync()` wrote field *names* into the ledger rather than the record, so the ledger could not
  rebuild the store - the one thing docs/11-history-authority.md requires of it. Events now carry the record.
  Events that carry no data are counted as skipped rather than guessed at.

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
