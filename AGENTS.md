# AGENTS.md

Instructions for an AI coding agent working in this repository. Read this file first, then only the documents
a task names. Everything here is normative.

## What this repository is

A specification repository. It contains documentation and three rendered deliverables. It contains **no
implementation code**, no build system and no test suite. A task that asks you to implement a feature is a
task that has not been scoped yet &mdash; say so rather than inventing an application.

## The three rules

1. **No AI in the critical path.** Read, write, sync, auth, search, report and notification must work with
   every AI container off. Any design that puts a model call on a request path is rejected.
2. **Nothing is silently overwritten.** Conflicts resolve by declared order and are written to the ledger with
   both candidates and the resolving rule.
3. **History has one authority.** The event ledger. Bi-temporal columns, git checkpoints and graph projections
   are derived and must be rebuildable. See [docs/11-history-authority.md](docs/11-history-authority.md).

## How to work here

- **Read the smallest set of documents that answers the question.** The map is [docs/index.md](docs/index.md).
- **Every number has one home.** If you need a metric, it is in [docs/10-metrics.md](docs/10-metrics.md).
  Do not restate it elsewhere; link to it. A second definition is a defect.
- **Every deliverable has one acceptance criterion.** It is in
  [docs/16-acceptance-criteria.md](docs/16-acceptance-criteria.md). A batch is done when the criterion passes,
  not when the text reads well.
- **Gaps are recorded, not invented.** If the specification does not answer something, add an entry to
  [docs/18-assumptions.md](docs/18-assumptions.md) with the next free `AS-NN` id, state the assumption, and
  name the defect it resolves. Do not silently pick a behaviour.
- **Unbounded absolutes are defects.** "Never", "always", "instant", "no perceptible" cannot be tested. Rewrite
  as a bounded claim with a number and a test.

## Writing rules

- Lead with the finding. A section opens with its conclusion, then supports it.
- No hype adjectives within a sentence of a number.
- Tables carry comparable facts, not prose. A cell needing a sentence belongs in the body.
- ASCII punctuation only in documents that will be rendered to PDF; the renderer sets Helvetica.
- Cite a defect id (`A-01`) when a passage closes one, and an assumption id (`AS-04`) when a passage relies on
  one.

## Verification before you commit

```bash
python3 scripts/linkcheck.py      # must print: ALL INTERNAL LINKS OK
```

There is no other check. Do not claim a document is verified unless that command ran and printed that line.

## What not to do

- Do not create placeholder files, stub documents or "coming soon" sections.
- Do not add CI that cannot pass, or a badge that does not reflect a real workflow.
- Do not claim a benchmark, a measurement or an audit that was not run.
- Do not introduce a second source of truth for a metric, an acceptance criterion or a decision.
- Do not move a v2 or v3 item into v1 scope without changing [docs/06-roadmap.md](docs/06-roadmap.md) entry
  criteria in the same commit.

## Before you call a change finished

1. `python3 -m unittest discover -s tests -t .` - and read the count.
2. `python3 scripts/linkcheck.py` - every relative link resolves.
3. `python3 scripts/check_docs.py` - the documentation and the landing page match the tree.
4. `python3 -m tessera.jargon` - no internal term reached user-facing text.
5. `python3 -m tessera.bench --gate` - nothing got three times slower.

A change that skips step 3 is not finished, however green steps 1 and 2 are.
