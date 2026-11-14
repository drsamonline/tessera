# 43 - Releasing

**Status: Draft**

A release is a tag, a note and a gate. The note is generated, the gate is a command, and the tag is the only part
somebody has to remember.

## The rule

> **A release is a tag on a commit where every gate passes, with notes generated from the tree.**

`scripts/release_notes.py` emits the body: a preamble that says what this is and what it is not, a table of the gates,
a stats block counted from the tree rather than typed, and the newest `CHANGELOG` section. Nothing in it is
maintained by hand, so it cannot be right about the version and wrong about the test count.

## The process

```
python3 scripts/check_docs.py          # VERSION matches the newest CHANGELOG entry
python3 -m unittest discover -s tests -t .
python3 -m tessera.fuzz
python3 -m tessera.bench --gate
git tag -a "v$(cat VERSION)" -m "TESSERA $(cat VERSION)"
git push origin "v$(cat VERSION)"
python3 scripts/release_notes.py > /tmp/notes.md
gh release create "v$(cat VERSION)" --notes-file /tmp/notes.md
```

`check_docs.py` is the first step because it is the one that catches a version that was never bumped - the same
drift it caught on its first run, when `VERSION` said `1.1.0` while the changelog was at `1.20.0`.

## This release

| | |
|---|---|
| Tag | `v1.25.0` |
| Tests | 692 |
| Documents | 43 |
| Dependencies | none |
| Defects found | 17, of which 16 are closed |

**It is the first tagged release, not the first version.** The changelog runs from 1.10 to 1.25 because each of those
was a real change; the tag is simply the first one that was cut.

## What a release note must not do

- **Must not claim production readiness.** The preamble says "not a product" before it says anything else, because a
  release page is the most-read page a repository has and the caveat has to be at the top of it.
- **Must not summarise a gap away.** "Not audited" is a line in the preamble, not a footnote.
- **Must not be hand-written.** A hand-written note drifts from the tree within two releases; a generated one can only
  drift if the generator does, and the generator reads the tree.

## What is not here

- **No automated release workflow.** The commands above are run by a person. A tag-triggered workflow that ran the
  gates and cut the release would be better and is not built.
- **No signed tags.** `git tag -a`, not `-s`.
- **No changelog enforcement on the tag.** `check_docs.py` compares `VERSION` to the newest `CHANGELOG` heading, but
  nothing stops a tag being cut on a commit where the gates fail; the process does, not the tooling.
- **No artifacts.** No wheel, no container pushed to a registry.
