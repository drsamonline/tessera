"""Projections: state derived from the ledger, and provably rebuildable.

docs/11-history-authority.md rules that the event ledger is the single authority
and that every other view of history is a projection which **must be rebuildable
from it**. This module is that projection, and `verify_rebuildable()` is the test
of the ruling.

Two views are produced from one pass over the log:

    current state   what the mesh believes now
    bi-temporal     what it believed at time T (valid time), and what it recorded
                    about that belief (transaction time)

The distinction is the product's central query, so it is worth being precise:

    valid time        when the fact was true in the world (the record's valid_from)
    transaction time  when the ledger learned it (the event's timestamp)

A correction that arrives late has a valid time in the past and a transaction
time now. Both are kept, which is why "what did we think last Tuesday" and "what
was actually true last Tuesday" are different questions with different answers.

No database. State is a dictionary, and the fingerprint is a hash of it, so two
projections agree or they do not.
"""

from __future__ import annotations

import hashlib
import json

from . import canonical


def _fingerprint(state: dict) -> str:
    blob = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Projection:
    """Materialised state, built by replaying the ledger."""

    def __init__(self, log, tenant_id: str):
        self.log = log
        self.tenant_id = tenant_id
        # object -> record id -> field -> value
        self.state: dict[str, dict[str, dict]] = {}
        # object -> record id -> field -> [(valid_from, tx_time, value)]
        self.temporal: dict[str, dict[str, dict]] = {}
        self.applied = 0
        self.skipped = 0

    # -- building ---------------------------------------------------------
    def build(self) -> "Projection":
        self.state, self.temporal, self.applied, self.skipped = {}, {}, 0, 0
        for event in self.log.events(self.tenant_id):
            self.apply(event)
        return self

    def apply(self, event: dict) -> None:
        payload = event.get("payload") or {}
        ref = event.get("canonical_ref") or ""
        if ":" not in ref:
            self.skipped += 1
            return
        object_name, record_id = canonical.parse_ref(ref)

        record = payload.get("record")
        if isinstance(record, dict):
            self._upsert(object_name, record_id, record, event)
            self.applied += 1
            return

        field = payload.get("field")
        if isinstance(field, str) and "value" in payload:
            self._patch(object_name, record_id, field, payload["value"], event)
            self.applied += 1
            return

        # An event that carries no data cannot be projected. It is counted, not
        # guessed at: a projection that invents state is worse than a gap.
        self.skipped += 1

    def _upsert(self, object_name: str, record_id: str, record: dict, event: dict) -> None:
        rows = self.state.setdefault(object_name, {}).setdefault(record_id, {})
        temporal = self.temporal.setdefault(object_name, {}).setdefault(record_id, {})
        for field, value in record.items():
            rows[field] = value
            temporal.setdefault(field, []).append((
                record.get("valid_from", ""), event.get("timestamp", ""), value,
            ))

    def _patch(self, object_name: str, record_id: str, field: str, value, event: dict) -> None:
        rows = self.state.setdefault(object_name, {}).setdefault(record_id, {})
        rows[field] = value
        temporal = self.temporal.setdefault(object_name, {}).setdefault(record_id, {})
        temporal.setdefault(field, []).append((
            event.get("timestamp", ""), event.get("timestamp", ""), value,
        ))

    # -- reading ----------------------------------------------------------
    def get(self, object_name: str, record_id: str) -> dict | None:
        return self.state.get(object_name, {}).get(record_id)

    def ids(self, object_name: str) -> list[str]:
        return sorted(self.state.get(object_name, {}))

    def count(self, object_name: str | None = None) -> int:
        if object_name is None:
            return sum(len(v) for v in self.state.values())
        return len(self.state.get(object_name, {}))

    def as_of(self, object_name: str, record_id: str, at: str) -> dict:
        """The record as the ledger knew it at transaction time `at`.

        Uses transaction time, not valid time: this answers "what did we know",
        which is the question a dispute asks.
        """
        out = {}
        temporal = self.temporal.get(object_name, {}).get(record_id, {})
        for field, versions in temporal.items():
            seen = None
            for _valid_from, tx_time, value in versions:
                if tx_time <= at:
                    seen = value
            if seen is not None:
                out[field] = seen
        return out

    def valid_at(self, object_name: str, record_id: str, valid_at: str) -> dict:
        """The record as it was true in the world at `valid_at`.

        Uses valid time. A late correction with an earlier valid_from changes
        this answer and leaves `as_of` alone, which is the whole point of
        keeping both.
        """
        out = {}
        temporal = self.temporal.get(object_name, {}).get(record_id, {})
        for field, versions in temporal.items():
            seen = None
            for valid_from, _tx_time, value in versions:
                if valid_from <= valid_at:
                    seen = value
            if seen is not None:
                out[field] = seen
        return out

    # -- the ruling, as a test -------------------------------------------
    def fingerprint(self) -> str:
        return _fingerprint(self.state)

    def verify_rebuildable(self) -> dict:
        """Rebuild from the ledger and compare.

        This is the enforcement of docs/11-history-authority.md: if a projection
        cannot be rebuilt from the log, the projection is a second source of
        truth wearing a disguise.
        """
        fresh = Projection(self.log, self.tenant_id).build()
        same = fresh.fingerprint() == self.fingerprint()
        return {
            "rebuildable": same,
            "live_fingerprint": self.fingerprint(),
            "rebuilt_fingerprint": fresh.fingerprint(),
            "live_records": self.count(),
            "rebuilt_records": fresh.count(),
            "events_applied": fresh.applied,
            "events_skipped": fresh.skipped,
        }
