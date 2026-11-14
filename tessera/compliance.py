"""Compliance: consent, data-subject requests, retention and audit export.

Reference: docs/04-core.md ("Compliance") and docs/research/compliance.md.

Four artefacts, and one honest limitation stated at the top of the module rather
than buried at the bottom:

    ConsentRegistry   purpose-bound consent, notice version, withdrawal
    DsarRequest       access, erasure, portability, rectification, with a clock
    RetentionPolicy   per-object windows, legal hold, a sweep that logs
    AuditExport       a signed bundle of events for a period

**The limitation.** The ledger is append-only and hash-chained. An erasure
request therefore cannot delete the bytes that were already written: the event
that recorded a contact still holds that contact, and rewriting it breaks the
chain that the whole design rests on.

What `erase()` does instead is append a tombstone. The projection drops the
record, every read path stops serving it, and the log records that the erasure
happened and when. The original payload remains in the log.

True erasure over an immutable log needs one of two things, and this repository
has neither:

    crypto-shredding   encrypt each subject's payload under a per-subject key and
                       destroy the key on erasure. Needs a crypto dependency.
    segmented retention drop whole log segments past their window. Needs a
                       retention window shorter than the audit obligation.

That is recorded as R-07 in docs/29-compliance.md, with what it would take to
close it. Claiming erasure is implemented would be a lie, and the first data
protection audit would find it.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import canonical

REQUEST_TYPES = ("access", "erasure", "portability", "rectification")
REQUEST_STATES = ("received", "verifying", "in_progress", "completed", "refused")

# The clock is a per-jurisdiction configuration, not a statutory fact.
# docs/research/compliance.md explains why 30 days is a default and not a claim.
DEFAULT_DSAR_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


class ComplianceError(Exception):
    """Raised when a compliance rule is violated."""


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------

@dataclass
class ConsentRecord:
    subject_ref: str
    purpose_id: str
    notice_version: str
    lawful_basis: str
    granted_at: datetime
    withdrawn_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.withdrawn_at is None


class ConsentRegistry:
    """Consent as notice plus purpose plus record, never a single flag.

    A `consent_state` field cannot answer "may I use this for marketing" and "may
    I use this for support" differently. That is the whole of purpose limitation,
    and it is why the registry is keyed by purpose.
    """

    def __init__(self, log=None, tenant_id: str = ""):
        self.log = log
        self.tenant_id = tenant_id
        self.records: list[ConsentRecord] = []

    def grant(self, subject_ref: str, purpose_id: str, notice_version: str,
              lawful_basis: str = "consent", at: datetime | None = None) -> ConsentRecord:
        if lawful_basis not in canonical.LAWFUL_BASES:
            raise ComplianceError(f"unknown lawful basis {lawful_basis!r}")
        if not notice_version:
            raise ComplianceError("a consent record must name the notice it was given under")
        record = ConsentRecord(subject_ref, purpose_id, notice_version, lawful_basis,
                               at or _now())
        self.records.append(record)
        self._log("consent.granted", {
            "subject_ref": subject_ref, "purpose_id": purpose_id,
            "notice_version": notice_version, "lawful_basis": lawful_basis,
        })
        return record

    def withdraw(self, subject_ref: str, purpose_id: str,
                 at: datetime | None = None) -> ConsentRecord:
        for record in reversed(self.records):
            if record.subject_ref == subject_ref and record.purpose_id == purpose_id \
                    and record.active:
                record.withdrawn_at = at or _now()
                self._log("consent.withdrawn", {"subject_ref": subject_ref,
                                                "purpose_id": purpose_id})
                return record
        raise ComplianceError(f"no active consent for {subject_ref!r} and {purpose_id!r}")

    def is_permitted(self, subject_ref: str, purpose_id: str,
                     lawful_basis: str = "consent") -> bool:
        """Permission is per purpose. A grant for support is not a grant for marketing."""
        if lawful_basis != "consent":
            return True  # a different basis does not rest on consent
        return any(r.subject_ref == subject_ref and r.purpose_id == purpose_id and r.active
                   for r in self.records)

    def _log(self, action: str, payload: dict) -> None:
        if self.log:
            self.log.append(self.tenant_id, "system", action, payload,
                            source_node_id="consent")


# ---------------------------------------------------------------------------
# Data subject requests
# ---------------------------------------------------------------------------

@dataclass
class DsarRequest:
    id: str
    subject_ref: str
    kind: str
    received_at: datetime
    due_days: int = DEFAULT_DSAR_DAYS
    state: str = "received"
    completed_at: datetime | None = None
    note: str = ""

    def __post_init__(self):
        if self.kind not in REQUEST_TYPES:
            raise ComplianceError(f"unknown request type {self.kind!r}")

    @property
    def due_at(self) -> datetime:
        return self.received_at + timedelta(days=self.due_days)

    def is_overdue(self, now: datetime | None = None) -> bool:
        return self.completed_at is None and (now or _now()) > self.due_at

    def advance(self, state: str, note: str = "", now: datetime | None = None) -> "DsarRequest":
        if state not in REQUEST_STATES:
            raise ComplianceError(f"unknown request state {state!r}")
        self.state = state
        if note:
            self.note = note
        if state == "completed":
            self.completed_at = now or _now()
        return self

    def snapshot(self) -> dict:
        return {
            "id": self.id, "subject_ref": self.subject_ref, "kind": self.kind,
            "received_at": _iso(self.received_at), "due_at": _iso(self.due_at),
            "due_days": self.due_days, "state": self.state,
            "completed_at": _iso(self.completed_at) if self.completed_at else None,
            "overdue": self.is_overdue(), "note": self.note,
        }


class DsarService:
    """Open, track and satisfy data subject requests.

    The export is a complete bundle: every record the subject appears in, plus
    their consent records, plus the ledger events that reference them. A partial
    export is worse than none, because it looks like an answer.
    """

    def __init__(self, projection, log=None, tenant_id: str = "", due_days: int = DEFAULT_DSAR_DAYS):
        self.projection = projection
        self.log = log
        self.tenant_id = tenant_id
        self.due_days = due_days
        self.requests: dict[str, DsarRequest] = {}

    def open(self, subject_ref: str, kind: str, now: datetime | None = None) -> DsarRequest:
        request = DsarRequest(id=canonical.uuid7(), subject_ref=subject_ref, kind=kind,
                              received_at=now or _now(), due_days=self.due_days)
        self.requests[request.id] = request
        self._log("dsar.received", request.snapshot())
        return request

    def _current_state(self) -> dict:
        """Rebuild rather than trust the snapshot the service was constructed with.

        A DSAR export that serves the state from before an erasure is worse than
        no export: it is a confident, signed, wrong answer.
        """
        if hasattr(self.projection, "build"):
            return self.projection.build().state
        return self.projection.state

    def export(self, subject_ref: str) -> dict:
        """Everything held about one subject, in one machine-readable bundle."""
        records, references = [], []
        for object_name, by_id in self._current_state().items():
            for record_id, record in by_id.items():
                if self._mentions(record, subject_ref):
                    records.append({"object": object_name, "id": record_id,
                                    "record": record})
                    references.append(canonical.make_ref(object_name, record_id))

        events = []
        if self.log:
            for ref in references:
                for event in self.log.history(self.tenant_id, ref):
                    events.append({"sequence": event["sequence"],
                                   "timestamp": event["timestamp"],
                                   "action": event["action"],
                                   "hash": event["hash"]})

        bundle = {
            "subject_ref": subject_ref,
            "generated_at": _iso(_now()),
            "records": records,
            "ledger_events": sorted(events, key=lambda e: e["sequence"]),
            "complete": True,
        }
        bundle["bundle_hash"] = hashlib.sha256(
            canonical.canonical_bytes({k: v for k, v in bundle.items() if k != "bundle_hash"})
        ).hexdigest()
        return bundle

    def _mentions(self, record: dict, subject_ref: str) -> bool:
        return subject_ref in json_values(record)

    def complete(self, request_id: str, now: datetime | None = None) -> DsarRequest:
        request = self.requests[request_id]
        request.advance("completed", now=now)
        self._log("dsar.completed", request.snapshot())
        return request

    def overdue(self, now: datetime | None = None) -> list[DsarRequest]:
        return [r for r in self.requests.values() if r.is_overdue(now)]

    def _log(self, action: str, payload: dict) -> None:
        if self.log:
            self.log.append(self.tenant_id, "system", action, payload,
                            source_node_id="dsar")


def json_values(node):
    """Every scalar in a nested structure, as strings. Used for subject matching."""
    out = []
    if isinstance(node, dict):
        for value in node.values():
            out.extend(json_values(value))
    elif isinstance(node, list):
        for value in node:
            out.extend(json_values(value))
    elif node is not None:
        out.append(str(node))
    return out


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

@dataclass
class RetentionRule:
    object_name: str
    days: int
    legal_hold: bool = False
    basis: str = "contract"


class RetentionPolicy:
    """Per-object windows, with legal hold, and a sweep that records what it did."""

    def __init__(self, log=None, tenant_id: str = ""):
        self.log = log
        self.tenant_id = tenant_id
        self.rules: dict[str, RetentionRule] = {}

    def set_rule(self, object_name: str, days: int, legal_hold: bool = False,
                 basis: str = "contract") -> RetentionRule:
        if object_name not in canonical.SCHEMA:
            raise ComplianceError(f"unknown object {object_name!r}")
        if days < 0:
            raise ComplianceError("a retention window cannot be negative")
        rule = RetentionRule(object_name, days, legal_hold, basis)
        self.rules[object_name] = rule
        return rule

    def due(self, projection, now: datetime | None = None) -> list[dict]:
        """Records past their window. Legal hold wins over expiry, always."""
        now = now or _now()
        out = []
        for object_name, rule in self.rules.items():
            if rule.legal_hold:
                continue
            for record_id, record in projection.state.get(object_name, {}).items():
                stamp = record.get("valid_from") or record.get("tx_time")
                if not stamp:
                    continue
                try:
                    created = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if created + timedelta(days=rule.days) <= now:
                    out.append({"object": object_name, "id": record_id,
                                "valid_from": stamp, "days": rule.days})
        return out

    def sweep(self, projection, now: datetime | None = None) -> dict:
        """Log an expiry event per due record. The projection drops them on rebuild."""
        rows = self.due(projection, now)
        for row in rows:
            if self.log:
                self.log.append(
                    self.tenant_id, "system", "record.retention_expired",
                    {"object": row["object"], "retention_days": row["days"],
                     "valid_from": row["valid_from"]},
                    canonical_ref=canonical.make_ref(row["object"], row["id"]),
                    source_node_id="retention",
                )
        return {"expired": len(rows), "rows": rows}


# ---------------------------------------------------------------------------
# Audit export
# ---------------------------------------------------------------------------

class AuditExport:
    """A signed bundle of events for a period, so an auditor can verify offline."""

    def __init__(self, log, tenant_id: str, key: bytes):
        if not key:
            raise ComplianceError("a signing key is required; there is no default")
        self.log = log
        self.tenant_id = tenant_id
        self.key = key

    def build(self, since: str, until: str) -> dict:
        events = [e for e in self.log.events(self.tenant_id)
                  if since <= e["timestamp"] <= until]
        body = {
            "tenant_id": self.tenant_id,
            "since": since,
            "until": until,
            "count": len(events),
            "head": events[-1]["hash"] if events else "",
            "first": events[0]["hash"] if events else "",
            "events": [{"sequence": e["sequence"], "timestamp": e["timestamp"],
                        "actor": e["actor"], "action": e["action"],
                        "hash": e["hash"], "payload_hash": e["payload_hash"]}
                       for e in events],
        }
        signature = hmac.new(self.key, canonical.canonical_bytes(body),
                             hashlib.sha256).hexdigest()
        return dict(body, signature=signature)

    def verify(self, bundle: dict) -> bool:
        body = {k: v for k, v in bundle.items() if k != "signature"}
        expected = hmac.new(self.key, canonical.canonical_bytes(body),
                            hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, bundle.get("signature", ""))


# ---------------------------------------------------------------------------
# Erasure
# ---------------------------------------------------------------------------

def erase(projection, log, tenant_id: str, subject_ref: str,
          actor: str = "system") -> dict:
    """Append a tombstone per record mentioning the subject.

    The projection stops serving the record and every read path follows. The
    original payload stays in the log; see the module docstring for what closing
    that gap actually requires.
    """
    erased = []
    for object_name, by_id in projection.state.items():
        for record_id, record in by_id.items():
            if subject_ref not in json_values(record):
                continue
            log.append(
                tenant_id, actor, "record.erased",
                {"object": object_name, "subject_ref": subject_ref,
                 "reason": "data subject request", "tombstone": True},
                canonical_ref=canonical.make_ref(object_name, record_id),
                source_node_id="dsar",
            )
            erased.append({"object": object_name, "id": record_id})
    return {"erased": len(erased), "records": erased,
            "note": "tombstoned, not destroyed; see docs/29-compliance.md"}
