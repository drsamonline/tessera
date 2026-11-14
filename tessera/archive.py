"""Segments, compaction and archival.

Reference: docs/11-history-authority.md, and the review's open question about a log
that grows without bound. Deliverable 8's last clause.

**An audit log does not compact, it archives.** Deleting old events is the one thing
a hash-chained record must not do: the chain is the proof, and a proof with a hole
in it is not a proof. So this module does three things instead:

    archive    copy a prefix of the chain into a segment file with its own manifest
    compact    replace that prefix in the live log with a single marker event whose
               prev_event_hash is the archived head - so the live chain still links
               to the archived one
    verify     both halves, independently, and the seam between them

The live log gets smaller and the proof survives. The archived segment verifies on
its own, the compacted log verifies from its marker, and the marker's
prev_event_hash is the arithmetic link between the two.
"""

from __future__ import annotations

import json
import os

from . import canonical, ledger


class ArchiveError(Exception):
    """Raised when a segment or a compaction is not sound."""


def _segment_name(first: int, last: int) -> str:
    return f"segment-{first:06d}-{last:06d}.jsonl"


def archive(log, tenant_id: str, directory: str, upto_sequence: int) -> dict:
    """Write the events up to and including `upto_sequence` into a segment.

    Nothing is removed. The segment is a copy plus a manifest, so archiving twice
    is harmless and archiving a segment you already have is a no-op.
    """
    events = [event for event in log.events(tenant_id)
              if event["sequence"] <= upto_sequence]
    if not events:
        raise ArchiveError(f"nothing to archive up to sequence {upto_sequence}")

    os.makedirs(directory, exist_ok=True)
    name = _segment_name(events[0]["sequence"], events[-1]["sequence"])
    path = os.path.join(directory, name)

    with open(path, "w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")

    manifest = {
        "tenant_id": tenant_id,
        "first_sequence": events[0]["sequence"],
        "last_sequence": events[-1]["sequence"],
        "count": len(events),
        "head_hash": events[0]["hash"],
        "tail_hash": events[-1]["hash"],
        "previous_hash": events[0]["prev_event_hash"],
        "segment": name,
    }
    manifest["checksum"] = canonical.canonical_hash(manifest)
    manifest_path = path.replace(".jsonl", ".manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)

    return manifest


def verify_segment(path: str) -> tuple[bool, list[str]]:
    """Verify a segment on its own: continuity, linkage, and every hash."""
    problems: list[str] = []
    manifest_path = path.replace(".jsonl", ".manifest.json")
    if not os.path.exists(manifest_path):
        return False, [f"{path}: no manifest"]

    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    expected = manifest.pop("checksum", "")
    if canonical.canonical_hash(manifest) != expected:
        problems.append("the manifest checksum does not match; it was altered")

    with open(path, encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle if line.strip()]

    if len(events) != manifest["count"]:
        problems.append(f"{manifest['segment']}: {len(events)} events, "
                        f"manifest says {manifest['count']}")
    if not events:
        return (not problems), problems

    if events[0]["hash"] != manifest["head_hash"]:
        problems.append("the first event does not match the manifest head")
    if events[-1]["hash"] != manifest["tail_hash"]:
        problems.append("the last event does not match the manifest tail")

    last_hash = events[0]["prev_event_hash"]
    last_seq = events[0]["sequence"] - 1
    for event in events:
        if event["sequence"] != last_seq + 1:
            problems.append(f"sequence gap at {event['sequence']}")
        if event["prev_event_hash"] != last_hash:
            problems.append(f"broken link at sequence {event['sequence']}")
        body = {k: v for k, v in event.items() if k != "hash"}
        if ledger._event_hash(body) != event["hash"]:
            problems.append(f"hash mismatch at sequence {event['sequence']}")
        last_hash = event["hash"]
        last_seq = event["sequence"]
    return (not problems), problems


def compact(log, tenant_id: str, directory: str, upto_sequence: int,
            actor: str = "system") -> dict:
    """Archive the prefix, then replace it in the live log with a marker.

    The marker carries the archived head hash as its `prev_event_hash`, so the
    compacted chain links to the archived one by arithmetic rather than by
    assertion.
    """
    manifest = archive(log, tenant_id, directory, upto_sequence)
    events = list(log.events(tenant_id))
    remaining = [event for event in events if event["sequence"] > upto_sequence]

    # The header is the first *line* of the compacted log and is not an event: it
    # carries no sequence and no hash, because it describes where the chain now
    # starts. Treating it as an event made its sequence collide with the first
    # surviving event.
    header = {
        ledger.MARKER: 1,
        "tenant_id": tenant_id,
        "archived_through": manifest["last_sequence"],
        "archived_tail": manifest["tail_hash"],
        "archived_head": manifest["head_hash"],
        "segment": manifest["segment"],
        "archived_count": manifest["count"],
        "actor": actor,
    }
    with open(log.path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(header, sort_keys=True, separators=(",", ":")) + "\n")
        for event in remaining:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        if log.durable:
            os.fsync(handle.fileno())
    log._load()
    return {"segment": manifest["segment"], "archived": manifest["count"],
            "archived_through": manifest["last_sequence"],
            "remaining": len(remaining) + 1}


def history(log, tenant_id: str, canonical_ref: str, directory: str) -> list[dict]:
    """A record's whole history, from the segments and the live log together.

    The caller should not have to know which half an event is in. That is the point
    of compaction: the log gets smaller, the answer does not change.
    """
    out = []
    if os.path.isdir(directory):
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".jsonl"):
                continue
            with open(os.path.join(directory, name), encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if (event["tenant_id"] == tenant_id
                            and event["canonical_ref"] == canonical_ref):
                        out.append(event)
    for event in log.events(tenant_id):
        if event["canonical_ref"] == canonical_ref:
            out.append(event)
    return sorted(out, key=lambda event: event["sequence"])
