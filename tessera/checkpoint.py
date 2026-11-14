"""Checkpoints over the ledger: diff and revert without rewriting history.

docs/11-history-authority.md: "git is a checkpoint log over the ledger, not a
per-write commit stream." This is that log.

The rule that makes it safe is simple and absolute: **a revert appends**. It does
not delete an event, truncate the file, or move a pointer backwards. Reverting to
a checkpoint writes compensating events that restore the earlier state, so the
ledger still contains everything that happened, including the revert. A history
you can rewrite is not a history.

Checkpoints are chained: each carries the hash of the one before it, so a
checkpoint file that has been edited fails verification the same way the ledger
does.
"""

from __future__ import annotations

import hashlib
import json
import os

from . import canonical
from .projection import Projection


def _hash(sequence: int, state: dict, parent: str) -> str:
    blob = json.dumps(
        {"sequence": sequence, "state": state, "parent": parent},
        sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Checkpointer:
    def __init__(self, log, tenant_id: str, path: str, every: int = 100):
        self.log = log
        self.tenant_id = tenant_id
        self.path = path
        self.every = every

    # -- reading ----------------------------------------------------------
    def checkpoints(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def head(self) -> dict | None:
        rows = self.checkpoints()
        return rows[-1] if rows else None

    def verify(self) -> tuple[bool, list[str]]:
        problems = []
        parent = ""
        for index, row in enumerate(self.checkpoints()):
            if row["parent"] != parent:
                problems.append(f"checkpoint {index}: parent hash does not match the previous")
            if _hash(row["sequence"], row["state"], row["parent"]) != row["hash"]:
                problems.append(f"checkpoint {index}: hash mismatch - the checkpoint was altered")
            parent = row["hash"]
        return (not problems, problems)

    # -- writing ----------------------------------------------------------
    def write(self, force: bool = False) -> dict | None:
        """Snapshot the projection if enough events have accumulated since the last one."""
        projection = Projection(self.log, self.tenant_id).build()
        sequence = projection.applied
        head = self.head()
        if not force and head and sequence - head["sequence"] < self.every:
            return None

        parent = head["hash"] if head else ""
        row = {
            "sequence": sequence,
            "state": projection.state,
            "parent": parent,
            "hash": _hash(sequence, projection.state, parent),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        return row

    # -- comparing --------------------------------------------------------
    def diff(self, index_a: int, index_b: int) -> dict:
        """What changed between two checkpoints, per record and per field."""
        rows = self.checkpoints()
        a, b = rows[index_a]["state"], rows[index_b]["state"]

        added, removed, changed = [], [], {}
        for object_name in sorted(set(a) | set(b)):
            a_ids = set(a.get(object_name, {}))
            b_ids = set(b.get(object_name, {}))
            for record_id in sorted(b_ids - a_ids):
                added.append(f"{object_name}:{record_id}")
            for record_id in sorted(a_ids - b_ids):
                removed.append(f"{object_name}:{record_id}")
            for record_id in sorted(a_ids & b_ids):
                left, right = a[object_name][record_id], b[object_name][record_id]
                fields = sorted(
                    f for f in set(left) | set(right) if left.get(f) != right.get(f)
                )
                if fields:
                    changed[f"{object_name}:{record_id}"] = fields

        return {"added": added, "removed": removed, "changed": changed}

    # -- reverting --------------------------------------------------------
    def revert_to(self, index: int, actor: str = "human") -> dict:
        """Restore the state at a checkpoint by appending compensating events.

        Nothing is deleted. The revert is itself a set of events, so `revert_to`
        shows up in the history and in the next diff.
        """
        rows = self.checkpoints()
        target = rows[index]["state"]
        current = Projection(self.log, self.tenant_id).build().state

        written = 0
        for object_name in sorted(set(target) | set(current)):
            target_records = target.get(object_name, {})
            current_records = current.get(object_name, {})
            for record_id in sorted(set(target_records) | set(current_records)):
                before = current_records.get(record_id, {})
                after = target_records.get(record_id, {})
                if before == after:
                    continue
                # An empty target means the record did not exist at the
                # checkpoint. Writing {"record": {}} would leave it in place with
                # its old fields, so the revert would silently do nothing. (R-09)
                payload = ({"record": after} if after
                           else {"tombstone": True, "reason": "reverted to a checkpoint"})
                self.log.append(
                    self.tenant_id, actor,
                    "record.revert" if after else "record.reverted_away",
                    payload,
                    canonical_ref=canonical.make_ref(object_name, record_id),
                    source_node_id="checkpoint",
                )
                written += 1

        return {"restored": written, "checkpoint": index, "sequence": rows[index]["sequence"]}
