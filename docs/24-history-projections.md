# 24 - Projections, checkpoints and the mirror

**Status: Draft**

[11-history-authority.md](11-history-authority.md) rules that the ledger is the single authority and that every
other view of history is a projection which must be rebuildable from it. Three projections now exist, and the
ruling is enforced by a test rather than by a paragraph.

## The three projections

| Module | What it derives | What it proves |
|---|---|---|
| `tessera/projection.py` | Current state, and two point-in-time views | A projection rebuilt from the log is byte-identical to the live one |
| `tessera/checkpoint.py` | Snapshots with a parent hash, diff, revert | Reverting appends; it never deletes |
| `tessera/mirror.py` | Markdown files plus a manifest of hashes | The mirror is a projection and its lag is a number |

## Two questions, two answers

The distinction the whole design exists for:

```
knew at 2026-11-02   asha@example.com
knew at 2026-11-05   a.rao@example.com
knew at 2026-11-11   asha.rao@example.com

true at 2026-11-01   asha@example.com
true at 2026-11-02   asha.rao@example.com
true at 2026-11-04   asha.rao@example.com
```

A correction on 10 November carries a valid time of 2 November. It changes what *was true* on 2 November and
leaves what we *knew* on 5 November untouched.

- `as_of(object, id, at)` answers "what did the ledger know at transaction time `at`". This is the question a
  dispute asks.
- `valid_at(object, id, at)` answers "what was true in the world at valid time `at`". This is the question a
  forecast asks.

Both are computed from one pass over the same events. A system that keeps only one of them can answer one
question and has to guess at the other.

## Rebuildable, or it is a second source of truth

```python
result = Projection(log, tenant).build().verify_rebuildable()
# {"rebuildable": True, "live_fingerprint": "ac1cc6ad...", "rebuilt_fingerprint": "ac1cc6ad..."}
```

The projection is fingerprinted, rebuilt from the log from scratch, and compared. Two consequences follow:

- A projection that cannot be rebuilt is a defect, not a design choice. The test says so.
- A projection that has been edited by hand fails the comparison, which is what `test_a_tampered_projection_is_not_rebuildable` asserts.

## Defect R-06, found by building this

The first version of `Mesh.sync()` wrote this into the ledger:

```python
{"fields": sorted(record)}          # the field NAMES
```

Field names cannot rebuild a record. The ledger was therefore unable to do the one thing
[11-history-authority.md](11-history-authority.md) requires of it, and the gap was invisible because nothing had
yet tried to project from it.

It now writes `{"record": record}`: the whole canonical record travels with the event. A production deployment
would store a content hash and a blob instead, to keep the log small, and would need a retention policy for the
blobs. At reference scale the record itself is the honest choice.

An event that carries no data - a conflict resolution, for instance - is counted as `skipped`, never guessed at.
A projection that invents state is worse than a gap, because the gap is visible.

## Checkpoints: diff and revert without rewriting history

A checkpoint is a snapshot of the projection with a parent hash, so checkpoints chain the way the ledger does and
a hand-edited checkpoint file fails verification.

`revert_to(index)` **appends** compensating events. It does not delete an event, truncate a file, or move a
pointer backwards. The demonstration:

```
revert       4 events before, 5 after - it appends, it never deletes
email now    asha.rao@example.com
chain        OK
```

The revert is itself in the history, so the next `diff` shows it. A history you can rewrite is not a history.

## The mirror, and lag as a number

`MarkdownMirror` writes one file per record with a field table and the record's full event history, plus a
`manifest.json` mapping each reference to a SHA-256 of the file it produced.

- `lag_events()` returns how many ledger events have landed since the mirror last ran. Not "eventually
  consistent" - a count.
- `verify()` re-hashes every file and reports what changed. A hand-edited mirror file is caught.
- Rebuilding from the same ledger produces the same bytes; `test_mirror_is_rebuildable` asserts it.

## What this does not do

- **No git binary.** The checkpoint log is git-shaped - content hashes, parent links, diff, revert by
  compensation - but it is not a git repository. Writing to a real git remote is a separate integration.
- **No object store.** The mirror writes to a local directory. S3 and a git remote are named in the
  specification and absent here.
- **No incremental projection.** Every read rebuilds from the log. At reference scale that is milliseconds; at
  a million events it is not, and a projection worker with a cursor is the next step.
- **No compaction.** The ledger grows without bound, which is correct for an audit log and needs a retention
  and archival policy before it is correct for a customer.

## Deliverable 8, updated

| Criterion | State |
|---|---|
| Any record's full write history reconstructable | Met |
| Revert restores prior state and is itself logged | Met |
| Mirror lag exposed as a metric | Met |
| Mirror failure does not fail a write | Met - the mirror reads the ledger, it is not on the write path |
| Asynchronous projection to object storage | **Not met** - local directory only |
