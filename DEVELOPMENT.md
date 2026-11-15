# Status: under development

**This project is not finished and not released.** It is published so the work can be inspected, not so it can be
adopted.

## What "under development" means here

| | |
|---|---|
| Version numbers | Build numbers, not stability promises. `v1.45.0` means the forty-fifth build, not "mature" |
| Releases | Every one is flagged **pre-release** on GitHub |
| API | May change without a deprecation cycle |
| Data | May be lost. There is no migration guarantee between builds |
| Support | None |

## What is finished

The specification, the reference implementation and the demo. 748 tests pass, four connectors conform to a 16-check
suite, the API serves, and one command starts both halves.

## What is not finished

The four items in [CLAIMS.md](CLAIMS.md) marked **not verified**, and the nine deliverables in
[docs/52-brief-conformance.md](docs/52-brief-conformance.md) marked **partial**.

### The gate: this project is finished when

- [ ] The Postgres DDL has been executed against a server, and the four RLS assertions pass
- [ ] One connector has completed a read-only sweep against a live tenant, and the responses are captured as fixtures
- [ ] The Android build has launched on a device and been used for one real task
- [ ] Every deliverable marked **partial** in the conformance document is either complete or moved to a recorded roadmap
      with entry criteria
- [ ] The four decisions in [docs/19-open-decisions.md](docs/19-open-decisions.md) are signed
- [ ] The four questions in [docs/53-licensing.md](docs/53-licensing.md#what-must-be-decided-before-the-first-invoice)
      are answered, because a commercial licence is on offer

**Nothing on that list is a documentation task.** Each one needs a credential, a database, a device or a signature.

## When it changes

This file is deleted, the pre-release flags come off, the banner comes off the README and the landing page, and the
version goes to 1.0.0 — in one commit, when every box above is ticked. Not before.
