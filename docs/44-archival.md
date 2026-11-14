# 44 - Archival and compaction

**Status: Draft**

Reference: [11-history-authority.md](11-history-authority.md), and the review's open question about a log that grows
without bound.

## An audit log does not compact, it archives

Deleting old events is the one thing a hash-chained record must not do: the chain is the proof, and a proof with a
hole in it is not a proof. So `tessera/archive.py` does three things instead.

| Operation | What it does |
|---|---|
| `archive()` | Copies a prefix of the chain into a segment file with its own manifest. Removes nothing |
| `compact()` | Archives, then replaces that prefix in the live log with a **header line** whose `archived_tail` is the segment's last hash |
| `verify_segment()` | Verifies a segment on its own: continuity, linkage, every hash, and the manifest checksum |

The live log gets smaller and the proof survives. The segment verifies independently, the compacted log verifies from
its header, and the header's `archived_tail` is the arithmetic link between them -
`test_the_marker_links_to_the_archived_tail` asserts the equality rather than trusting the comment.

## The header is not an event

The first design made the compaction marker an *event* with a sequence number. Its sequence collided with the first
surviving event's, and the archive tests found it immediately: `expected 17, found 16`.

A header line carries no sequence and no hash, because it describes where the chain now *starts*. Three readers had
to learn that, and each is a place the bug could have hidden:

- `events()` - skips it, or a caller sees a dict with no `payload`
- `read_from()` - skips it, or an incremental projection is handed a non-event
- `verify()` - seeds `last_hash` and `last_seq` from it, or every compacted ledger reports a broken link at line two

`test_an_incremental_projection_reads_a_compacted_log` is the one that would have been missed by hand: the projection
and the archive were written weeks apart.

## What compaction preserves

| Property | Test |
|---|---|
| The compacted log verifies | `test_compaction_shrinks_the_live_log_and_keeps_it_verifiable` |
| The segment verifies on its own | `test_the_segment_still_verifies_after_compaction` |
| New events still chain onto the header | `test_new_events_after_compaction_still_chain` |
| A second compaction is sound | `test_a_second_compaction_is_sound` |
| A record's history spans both halves, in order | `test_history_is_ordered_across_the_seam` |
| Tampering is still caught | `test_verify_still_catches_tampering_after_compaction` |
| A tampered segment is caught | `test_a_tampered_segment_fails` |
| A tampered manifest is caught | `test_a_tampered_manifest_fails` |

`history()` reads the segments and the live log and returns one ordered list. The caller should not have to know
which half an event is in - that is the point of compaction: the log gets smaller, the answer does not change.

## What is not here

- **No retention policy.** `compact()` is called with a sequence number by an operator. Nothing decides when.
- **No automatic scheduling.** No cron, no timer.
- **No compression.** Segments are plain JSON Lines; they compress well and nothing compresses them.
- **No external anchor.** The whole scheme is tamper-*evident* only against someone who does not control the
  directory. `docs/11-history-authority.md` specifies publishing the chain head somewhere else and this does not.
- **No pruning of segments.** An archive that grows forever has moved the problem, not solved it; deleting a segment
  would need the external anchor first.
