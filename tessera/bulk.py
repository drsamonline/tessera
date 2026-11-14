"""Boring features: CSV import, bulk operations, backup and restore.

Reference: docs/17-constraints.md ("The boring features"). Deliverable 10.

These are the features that make a buyer believe the product is real: import a
file, change a hundred records and undo it, take a backup and go back to it. None
of them is interesting and all of them are load-bearing.

Every one writes to the ledger, so "who imported this" and "who undid it" are
answered by the same structure as everything else.
"""

from __future__ import annotations

import csv
import io
import json

from . import canonical


class BulkError(Exception):
    """Raised when an import, a bulk operation or a restore cannot proceed."""


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

def preview(csv_text: str, object_name: str, mapping: dict[str, str],
            defaults: dict | None = None) -> dict:
    """Dry run: map, validate, report. Writes nothing.

    `mapping` maps a CSV column to a canonical field. A column not in the mapping
    is ignored; a canonical field not in the mapping keeps its default.

    The dry run applies the same defaults the commit will, so the preview shows
    what the commit will actually do. A preview that validates a different
    payload from the one that gets written is a preview nobody can trust.
    """
    if object_name not in canonical.SCHEMA:
        raise BulkError(f"unknown object {object_name!r}")

    reader = csv.DictReader(io.StringIO(csv_text))
    rows, problems = [], []
    for index, raw in enumerate(reader, start=2):  # 2 = first data row after the header
        payload = dict(defaults or {}, **_map_row(raw, mapping))
        # the commit mints an id for a row that has none, so the dry run does too;
        # otherwise the preview validates a payload that will never be written
        payload.setdefault("id", canonical.uuid7())
        issues = canonical.validate(object_name, payload)
        if issues:
            problems.append({"row": index, "issues": issues[:3]})
        else:
            rows.append(payload)
    return {
        "object": object_name,
        "rows": rows,
        "problems": problems,
        "ready": len(rows),
        "rejected": len(problems),
        "columns_seen": list(reader.fieldnames or []),
    }


def _map_row(raw: dict, mapping: dict[str, str]) -> dict:
    payload = {}
    for column, field_name in mapping.items():
        if column in raw and raw[column] not in (None, ""):
            payload[field_name] = raw[column]
    return payload


class Importer:
    """Import a CSV, and roll the whole batch back if it was wrong."""

    def __init__(self, log, tenant_id: str):
        self.log = log
        self.tenant_id = tenant_id
        self.batches: dict[str, list[str]] = {}

    def commit(self, csv_text: str, object_name: str, mapping: dict[str, str],
               defaults: dict | None = None, actor: str = "human") -> dict:
        """Import the valid rows. Rejected rows are reported, never guessed at."""
        result = preview(csv_text, object_name, mapping, defaults)
        batch_id = canonical.uuid7()
        imported = []

        for payload in result["rows"]:
            merged = dict(payload)
            record_id = merged.get("id") or canonical.uuid7()
            merged["id"] = record_id
            merged.setdefault("tenant_id", self.tenant_id)
            merged.setdefault("valid_from", "")
            merged.setdefault("tx_time", "")
            merged.setdefault("consent_state", "pending")
            merged.setdefault("lawful_basis", "legitimate_interest")
            merged.setdefault("purpose_id", "")
            merged.setdefault("retention_policy_id", "")

            self.log.append(self.tenant_id, actor, f"{object_name.lower()}.import",
                            {"record": merged, "batch": batch_id},
                            canonical_ref=canonical.make_ref(object_name, record_id),
                            source_node_id="import")
            imported.append(record_id)

        self.batches[batch_id] = [f"{object_name}:{rid}" for rid in imported]
        return {"batch": batch_id, "imported": len(imported),
                "rejected": result["rejected"], "problems": result["problems"]}

    def rollback(self, batch_id: str, actor: str = "human") -> dict:
        """Tombstone everything a batch created. The import stays in the history."""
        if batch_id not in self.batches:
            raise BulkError(f"unknown batch {batch_id!r}")
        refs = self.batches.pop(batch_id)
        for ref in refs:
            self.log.append(self.tenant_id, actor, "import.rolled_back",
                            {"tombstone": True, "batch": batch_id, "reason": "import rollback"},
                            canonical_ref=ref, source_node_id="import")
        return {"rolled_back": len(refs), "batch": batch_id}


# ---------------------------------------------------------------------------
# Bulk operations, with undo
# ---------------------------------------------------------------------------

class BulkUpdate:
    """Change many records at once, and undo it as one operation."""

    def __init__(self, log, tenant_id: str):
        self.log = log
        self.tenant_id = tenant_id
        self.undo_tokens: dict[str, list[tuple[str, str, object]]] = {}

    def apply(self, refs: list[str], field_name: str, value, actor: str = "human") -> dict:
        if not refs:
            raise BulkError("a bulk operation with no records is not an operation")
        token = canonical.uuid7()
        previous: list[tuple[str, str, object]] = []

        for ref in refs:
            canonical.parse_ref(ref)
            previous.append((ref, field_name, None))  # prior value is read from the log
            self.log.append(self.tenant_id, actor, "bulk.update",
                            {"field": field_name, "value": value, "token": token},
                            canonical_ref=ref, source_node_id="bulk")

        self.undo_tokens[token] = previous
        return {"token": token, "changed": len(refs), "field": field_name}

    def undo(self, token: str, previous: dict[str, object], actor: str = "human") -> dict:
        """Restore the values the caller read before the operation.

        The undo token carries the *references*, and the caller supplies the prior
        values it read. Storing them here would make this a second source of truth
        for state, which is the thing the ledger exists to prevent.
        """
        if token not in self.undo_tokens:
            raise BulkError(f"unknown undo token {token!r}")
        rows = self.undo_tokens.pop(token)
        restored = 0
        for ref, field_name, _prior in rows:
            if ref not in previous:
                continue
            self.log.append(self.tenant_id, actor, "bulk.undo",
                            {"field": field_name, "value": previous[ref], "token": token},
                            canonical_ref=ref, source_node_id="bulk")
            restored += 1
        return {"restored": restored, "token": token}


# ---------------------------------------------------------------------------
# Backup and restore
# ---------------------------------------------------------------------------

class Backup:
    """Point-in-time backup of the ledger, and a restore that verifies first."""

    def __init__(self, log, tenant_id: str):
        self.log = log
        self.tenant_id = tenant_id

    def create(self, upto_sequence: int | None = None) -> dict:
        events = [e for e in self.log.events(self.tenant_id)
                  if upto_sequence is None or e["sequence"] <= upto_sequence]
        body = {
            "tenant_id": self.tenant_id,
            "sequence": events[-1]["sequence"] if events else 0,
            "head": events[-1]["hash"] if events else "",
            "count": len(events),
            "events": events,
        }
        body["checksum"] = canonical.canonical_hash(
            {k: v for k, v in body.items() if k != "checksum"})
        return body

    def to_bytes(self, upto_sequence: int | None = None) -> bytes:
        return json.dumps(self.create(upto_sequence), sort_keys=True).encode("utf-8")

    def restore(self, blob: bytes, path: str) -> dict:
        """Write a new ledger from a backup, after checking the checksum and the chain.

        A restore that trusts its input is a restore that can be handed a forged
        backup and quietly replace a customer's history.
        """
        bundle = json.loads(blob.decode("utf-8"))
        expected = bundle.pop("checksum", "")
        if canonical.canonical_hash(bundle) != expected:
            raise BulkError("the backup checksum does not match; the file was altered")

        from .ledger import EventLog
        restored = EventLog(path, durable=True)
        with open(path, "w", encoding="utf-8") as handle:
            for event in bundle["events"]:
                handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        restored._load()

        ok, problems = restored.verify()
        if not ok:
            raise BulkError(f"the restored chain does not verify: {problems[:3]}")
        return {"restored": len(bundle["events"]), "sequence": bundle["sequence"],
                "head": bundle["head"]}
