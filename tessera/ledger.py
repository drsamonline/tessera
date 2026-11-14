"""The universal event ledger.

This is the single authority for history. Bi-temporal columns, git checkpoints
and graph projections are derived from it and must be rebuildable from it.

Reference: docs/11-history-authority.md.

Design notes
------------
* Append-only JSON Lines. One event per line, never rewritten. `verify()`
  recomputes every hash from the stored body, so a rewritten line is detected.
* Per-tenant sequence numbers. A tenant's chain is independent of every other
  tenant's, which is what makes "what did each system know at time T" a bounded
  query rather than a scan of the world.
* Each event carries its own `hash`. The specification lists `prev_event_hash`
  but not a self-hash; a chain is verifiable without one (recompute and compare
  against the next event's `prev_event_hash`), but storing it makes verification
  unambiguous and lets an anchor be published without re-reading the whole log.
  This is an implementation addition, recorded here rather than assumed.
* The payload is retained alongside its hash. The hash is what the chain covers;
  the payload is what makes the point-in-time query answerable without a second
  store. A deployment that must not retain payloads drops them and keeps the
  hash, at the cost of that query.
* Single-writer assumption. A production deployment serialises appends per
  tenant; this reference implementation does not lock, and says so.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from . import canonical

GENESIS = "0" * 64


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _event_hash(body: dict) -> str:
    return canonical.canonical_hash(body)


class LedgerError(Exception):
    """Raised when the log cannot accept a write or fails verification."""


class EventLog:
    """An append-only, hash-chained event log."""

    def __init__(self, path: str, durable: bool = True):
        self.path = path
        # `durable=True` fsyncs after every append. It costs a fraction of a
        # millisecond and it is the difference between "the ledger is the record"
        # and "the ledger is the record until the machine loses power". It
        # defaults to on: a deployment that wants speed over durability has to
        # say so, which is the right way round. (R-12)
        self.durable = durable
        self._heads: dict[str, str] = {}      # tenant_id -> last event hash
        self._seq: dict[str, int] = {}        # tenant_id -> last sequence
        self._load()

    # -- reading -----------------------------------------------------------
    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                tenant = event["tenant_id"]
                self._heads[tenant] = event["hash"]
                self._seq[tenant] = event["sequence"]

    def read_from(self, offset: int = 0, tenant_id: str | None = None):
        """Yield events from a byte offset, plus the offset to resume from.

        This is what makes a projection incremental: an append-only file has a
        stable prefix, so a worker that remembers where it stopped reads only the
        bytes that arrived since. Without it every read replays the whole log,
        which is O(n) per request and does not survive a million events. (O-05,
        O-06 in docs/31-code-review.md)
        """
        if not os.path.exists(self.path):
            return [], offset
        out = []
        with open(self.path, "rb") as f:
            f.seek(offset)
            for raw in f:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                event = json.loads(line)
                if tenant_id is None or event["tenant_id"] == tenant_id:
                    out.append(event)
            new_offset = f.tell()
        return out, new_offset

    def size(self) -> int:
        return os.path.getsize(self.path) if os.path.exists(self.path) else 0

    def events(self, tenant_id: str | None = None):
        """Yield stored events in write order, optionally for one tenant."""
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                if tenant_id is None or event["tenant_id"] == tenant_id:
                    yield event

    # -- writing -----------------------------------------------------------
    def append(
        self,
        tenant_id: str,
        actor: str,
        action: str,
        payload: dict,
        canonical_ref: str = "",
        source_node_id: str = "",
        evidence_refs: list[str] | None = None,
        timestamp: str | None = None,
    ) -> dict:
        """Append one event and return it.

        `actor` is one of human, agent, system. The actor is recorded, not
        inferred: an event that cannot name who acted is not admissible.
        """
        if actor not in ("human", "agent", "system"):
            raise LedgerError(f"actor must be human, agent or system, got {actor!r}")
        if canonical_ref:
            canonical.parse_ref(canonical_ref)  # raises on a malformed reference

        sequence = self._seq.get(tenant_id, 0) + 1
        prev = self._heads.get(tenant_id, GENESIS)

        body = {
            "id": canonical.uuid7(),
            "tenant_id": tenant_id,
            "actor": actor,
            "source_node_id": source_node_id,
            "canonical_ref": canonical_ref,
            "action": action,
            "payload": payload,
            "payload_hash": canonical.canonical_hash(payload),
            "evidence_refs": list(evidence_refs or []),
            "timestamp": timestamp or _now(),
            "sequence": sequence,
            "prev_event_hash": prev,
        }
        event = dict(body, hash=_event_hash(body))

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            f.flush()
            if self.durable:
                os.fsync(f.fileno())

        self._heads[tenant_id] = event["hash"]
        self._seq[tenant_id] = sequence
        return event

    # -- verification ------------------------------------------------------
    def verify(self, tenant_id: str | None = None,
               anchor: dict | None = None) -> tuple[bool, list[str]]:
        """Recompute the chain. Returns (ok, problems).

        Checks, per tenant: sequence continuity, linkage to the previous hash, and
        that the stored hash matches the stored body.

        `anchor` is `{"sequence": n, "hash": h}` from a checkpoint, and it makes
        the check incremental: events at or before the anchor are skipped and the
        chain is continued from a hash already known to be good.

        **An incremental check cannot see a rewrite before the anchor.** That is
        the trade, and it is why the anchor must come from somewhere the database
        owner does not control - the external anchor in
        docs/11-history-authority.md. A full verify is still the thing to run
        weekly.
        """
        problems: list[str] = []
        last_hash: dict[str, str] = {}
        last_seq: dict[str, int] = {}
        if anchor:
            for tenant in ([tenant_id] if tenant_id else list(self._heads)):
                last_hash[tenant] = anchor["hash"]
                last_seq[tenant] = anchor["sequence"]

        for event in self.events(tenant_id):
            tenant = event["tenant_id"]
            if anchor and event["sequence"] <= anchor["sequence"]:
                continue
            expected_seq = last_seq.get(tenant, 0) + 1
            if event["sequence"] != expected_seq:
                problems.append(
                    f"{tenant}: sequence gap at event {event['id']} "
                    f"(expected {expected_seq}, found {event['sequence']})"
                )
            expected_prev = last_hash.get(tenant, GENESIS)
            if event["prev_event_hash"] != expected_prev:
                problems.append(
                    f"{tenant}: broken link at event {event['id']} "
                    f"(prev_event_hash does not match the preceding event)"
                )
            body = {k: v for k, v in event.items() if k != "hash"}
            if _event_hash(body) != event["hash"]:
                problems.append(
                    f"{tenant}: hash mismatch at event {event['id']} - the record was altered"
                )
            if canonical.canonical_hash(event["payload"]) != event["payload_hash"]:
                problems.append(
                    f"{tenant}: payload hash mismatch at event {event['id']}"
                )
            last_hash[tenant] = event["hash"]
            last_seq[tenant] = event["sequence"]

        return (not problems, problems)

    # -- anchoring ---------------------------------------------------------
    def anchor(self) -> dict:
        """Return the current head hash and length of every tenant chain.

        A chain head is only tamper-evident against someone who does not control
        the database once it has been published somewhere else. Publish this.
        """
        heads = {}
        for tenant in self._heads:
            heads[tenant] = {"head": self._heads[tenant], "length": self._seq[tenant]}
        return {"at": _now(), "heads": heads}

    def write_anchor(self, path: str) -> dict:
        """Append the current anchor to an anchor file and return it."""
        record = self.anchor()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return record

    # -- the central query -------------------------------------------------
    def knows_at(self, tenant_id: str, canonical_ref: str, at: str) -> dict:
        """What each node knew about `canonical_ref` at time `at`.

        This is the product's central question, and it is answered here and
        nowhere else. Returns {source_node_id: payload} for the last event each
        source wrote at or before `at`.
        """
        horizon = canonical.parse_time(at)
        known: dict[str, dict] = {}
        for event in self.events(tenant_id):
            if event["canonical_ref"] != canonical_ref:
                continue
            if canonical.parse_time(event["timestamp"]) > horizon:
                # Not a `break`: the log is ordered by append, and a late-arriving
                # event may carry an earlier timestamp than one already written.
                # A point-in-time query therefore filters; it does not seek.
                continue
            known[event["source_node_id"] or "native"] = event["payload"]
        return known

    def history(self, tenant_id: str, canonical_ref: str) -> list[dict]:
        """Every event recorded against one canonical reference, in order."""
        return [e for e in self.events(tenant_id) if e["canonical_ref"] == canonical_ref]
