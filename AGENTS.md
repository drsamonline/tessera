# AGENTS.md

Instructions for an AI coding agent working in this repository. Read this file first, then only the documents
a task names. Everything here is normative.

## What this repository is

Three things, and the difference matters when you are asked to change something:

| Part | Where | State |
|---|---|---|
| The specification | `docs/` — 52 documents | The design. Every claim is a requirement |
| The reference implementation | `tessera/` — 40 modules, stdlib only | Runs. 748 tests |
| The demo | `python3 -m tessera.demo` | Starts the API and the console together on free ports |

This file said "no implementation code, no build system and no test suite" until 15 November 2026, long after all
three existed. An agent that read it would have refused to work on the code that was there. **If a document in this
repository describes a repository you cannot see, the document is wrong — check the code and fix the document.**

## The three rules

1. **No AI in the critical path.** Read, write, sync, auth, search, report and notification must work with
   every AI container off. Any design that puts a model call on a request path is rejected.
2. **Nothing is silently overwritten.** Conflicts resolve by declared order and are written to the ledger with
   both candidates and the resolving rule.
3. **History has one authority.** The event ledger. Bi-temporal columns, git checkpoints and graph projections
   are derived and must be rebuildable. See [docs/11-history-authority.md](docs/11-history-authority.md).

## The verification gate

**No claim of done, fixed, passing or shipped without a command run after the last edit, and its output read.**

| Claim | The command that proves it |
|---|---|
| The tests pass | `python3 -m unittest discover -s tests -t .` |
| Documentation matches the code | `python3 scripts/check_docs.py` |
| Every public claim still holds | `python3 scripts/check_claims.py` |
| The connectors conform | `python3 scripts/conformance_report.py` |
| The DDL is valid Postgres | `python3 scripts/validate_ddl.py` |
| Every module still answers | `python3 scripts/smoke.py` |
| Internal links resolve | `python3 scripts/linkcheck.py` |

A check you have not seen fail is not a check. When you add one, run it against a deliberately broken copy and confirm
it fails. Two examples of that discipline already in the repository:
`tests/test_ddl.py::test_the_parser_rejects_a_broken_statement` and `tests/test_tenants.py` — the isolation tests were
written to fail against a shared mesh before the router existed.

Never report a command's success when you only saw its exit code. Read the output, or you have not verified anything.

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
