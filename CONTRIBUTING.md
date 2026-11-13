# Contributing to TESSERA

> **Project status: specification only.** No implementation code exists. This guide describes how the repository
> is actually run today.
> **Last verified:** 2026-11-14 against the initial commit.

## Ground rules (non-negotiable)

1. **Honesty over polish.** Never claim a document, measurement, test or audit succeeded unless it ran. Never
   fabricate numbers, contacts, response times or CI runs.
2. **No placeholder files.** Do not create empty or stub documents "for later". If something does not exist,
   prose says so.
3. **One source of truth per fact.** A metric lives in [docs/10-metrics.md](docs/10-metrics.md). An acceptance
   criterion lives in [docs/16-acceptance-criteria.md](docs/16-acceptance-criteria.md). A decision lives in
   [docs/19-open-decisions.md](docs/19-open-decisions.md). Restating one of these elsewhere is a defect, not a
   convenience.
4. **Never commit credentials.** Tokens, keys and passwords do not go into commits, remote URLs or documents.
5. **Unbounded absolutes are defects.** "Never", "always", "instant" and "no perceptible" cannot be tested.
   Rewrite as a bounded claim with a number and a test.

## The only check

```bash
python3 scripts/linkcheck.py     # must print: ALL INTERNAL LINKS OK
```

There is no test suite, linter or build. Do not add CI that cannot pass, and do not add a badge that does not
reflect a real workflow.

## Changing the specification

1. Read [docs/index.md](docs/index.md) and the document you intend to change.
2. If the change closes a defect, cite its id in the passage (`Closes C-03.`).
3. If the change relies on an assumption, add it to [docs/18-assumptions.md](docs/18-assumptions.md) with the
   next free `AS-NN` id.
4. If the change alters scope, update [docs/06-roadmap.md](docs/06-roadmap.md) entry criteria in the same commit.
5. Run the link check. Commit as `docs: <scope> - <summary>`.

## Pull requests

Use [.github/pull_request_template.md](.github/pull_request_template.md) and answer every section honestly.
"not run" is an acceptable answer for checks that do not exist.

## Licensing of contributions

TESSERA is licensed **PolyForm Noncommercial 1.0.0** ([LICENSE](LICENSE)) &mdash; source-available, not
OSI-approved open source; commercial use needs a separate licence.

By submitting a patch, issue or pull request you agree that:

1. you have the right to submit it, and it is your own work or properly attributed;
2. it is licensed to this project under the same terms as the project;
3. you are not granting the project permission to relicense your contribution commercially on your behalf.

If you cannot agree to (2), open an issue describing the change instead of sending a patch.
