"""The Markdown mirror: a readable projection, written asynchronously.

docs/14-deterministic-features.md lists "Continuous Markdown mirror - async
projection, lag exposed as a metric". This is it, without the object store: files
on disk, a manifest with a hash per file, and a lag measured in ledger events
rather than in optimistic prose.

The mirror is a projection and nothing reads from it. If it is deleted, the next
run rebuilds it. If it disagrees with the ledger, the ledger is right and the
mirror is stale, which is why the manifest records the sequence it was built at.
"""

from __future__ import annotations

import hashlib
import json
import os

from . import canonical
from .projection import Projection

HEADER = """---
object: {object_name}
id: {record_id}
ledger_sequence: {sequence}
generated: rebuild from the ledger; this file is a projection
---
"""


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


class MarkdownMirror:
    def __init__(self, log, tenant_id: str, out_dir: str):
        self.log = log
        self.tenant_id = tenant_id
        self.out_dir = out_dir

    def path_for(self, object_name: str, record_id: str) -> str:
        return os.path.join(self.out_dir, _safe(object_name), f"{_safe(record_id)}.md")

    # -- writing ----------------------------------------------------------
    def mirror(self) -> dict:
        """Rewrite every record file. Returns counts, never raises on a bad record."""
        projection = Projection(self.log, self.tenant_id).build()
        os.makedirs(self.out_dir, exist_ok=True)

        written = 0
        for object_name in sorted(projection.state):
            directory = os.path.join(self.out_dir, _safe(object_name))
            os.makedirs(directory, exist_ok=True)
            for record_id in sorted(projection.state[object_name]):
                record = projection.state[object_name][record_id]
                path = self.path_for(object_name, record_id)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._render(object_name, record_id, record, projection.applied))
                written += 1

        manifest = {
            "sequence": projection.applied,
            "files": {
                f"{object_name}:{record_id}": self._digest(object_name, record_id)
                for object_name in projection.state
                for record_id in projection.state[object_name]
            },
        }
        with open(os.path.join(self.out_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
        return {"files": written, "sequence": projection.applied}

    def _render(self, object_name: str, record_id: str, record: dict, sequence: int) -> str:
        lines = [HEADER.format(object_name=object_name, record_id=record_id,
                               sequence=sequence)]
        lines.append(f"# {object_name}: {record.get('full_name') or record.get('name') or record_id}")
        lines.append("")
        lines.append("| field | value |")
        lines.append("|---|---|")
        for field in sorted(record):
            value = record[field]
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True)
            lines.append(f"| `{field}` | {value} |")
        lines.append("")
        lines.append("## History")
        lines.append("")
        lines.append("| sequence | time | actor | action |")
        lines.append("|---|---|---|---|")
        ref = canonical.make_ref(object_name, record_id)
        for event in self.log.history(self.tenant_id, ref):
            lines.append(
                f"| {event['sequence']} | {event['timestamp']} | {event['actor']} "
                f"| {event['action']} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _digest(self, object_name: str, record_id: str) -> str:
        path = self.path_for(object_name, record_id)
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    # -- reading ----------------------------------------------------------
    def manifest(self) -> dict:
        path = os.path.join(self.out_dir, "manifest.json")
        if not os.path.exists(path):
            return {"sequence": 0, "files": {}}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def lag_events(self) -> int:
        """Ledger events written since the mirror last ran.

        A number, not an adjective. A mirror that is behind by 4,000 events is
        behind by 4,000 events, and the operator can see it.
        """
        current = sum(1 for _ in self.log.events(self.tenant_id))
        return max(0, current - self.manifest().get("sequence", 0))

    def verify(self) -> dict:
        """Does every file still hash to what the manifest recorded?"""
        manifest = self.manifest()
        missing, changed = [], []
        for ref, digest in manifest.get("files", {}).items():
            object_name, _, record_id = ref.partition(":")
            path = self.path_for(object_name, record_id)
            if not os.path.exists(path):
                missing.append(ref)
            elif self._digest(object_name, record_id) != digest:
                changed.append(ref)
        return {"ok": not missing and not changed, "missing": missing, "changed": changed}
