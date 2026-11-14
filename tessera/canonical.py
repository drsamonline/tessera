"""Canonical schema for TESSERA.

The canonical schema is the contract every connector speaks. It is versioned:
a connector declares which version it implements, and a version bump requires a
migration path plus a conformance re-run before any connector is upgraded.

Reference: docs/03-mesh.md ("Canonical schema").

This module is deliberately dependency-free. It defines the schema, validates a
payload against it, and produces the canonical hash the ledger chains on.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def uuid7(ms: int | None = None, rand: bytes | None = None) -> str:
    """Return a UUIDv7 (RFC 9562): 48-bit millisecond timestamp, then randomness.

    Time-ordered identifiers are what make the ledger and the graph overlays
    cheap to build: sorting by id is sorting by creation time, so a projection
    worker can resume from a cursor instead of a scan.
    """
    if ms is None:
        ms = int(time.time() * 1000)
    if rand is None:
        rand = os.urandom(10)
    if len(rand) != 10:
        raise ValueError("rand must be 10 bytes")

    ts = ms & ((1 << 48) - 1)
    b = bytearray(16)
    b[0:6] = ts.to_bytes(6, "big")
    # version 7 in the high nibble of byte 6, 12 random bits below it
    b[6] = 0x70 | (rand[0] & 0x0F)
    b[7] = rand[1]
    # variant 10 in the top bits of byte 8, 62 random bits below it
    b[8] = 0x80 | (rand[2] & 0x3F)
    b[9:16] = rand[3:10]

    h = b.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def uuid7_timestamp(value: str) -> int:
    """Extract the millisecond timestamp from a UUIDv7 string."""
    return int(value.replace("-", "")[0:12], 16)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
# Field kinds: "str", "int", "num", "bool", "uuid", "time" (ISO-8601 str),
# "ref" (a canonical reference, "<Object>:<uuid>"), "list", "dict".
# "req" marks a required field; everything else is optional.

_ENVELOPE = {
    "id": ("uuid", True),
    "tenant_id": ("uuid", True),
    "valid_from": ("time", True),
    "valid_to": ("time", False),
    "tx_time": ("time", True),
    "consent_state": ("str", True),
    "lawful_basis": ("str", True),
    "purpose_id": ("str", True),
    "retention_policy_id": ("str", True),
    # any record can be owned by a seat; row-level access control depends on it
    "owner_seat_id": ("uuid", False),
}

CONSENT_STATES = ("granted", "withdrawn", "pending", "not_required")
LAWFUL_BASES = ("consent", "contract", "legal_obligation", "vital_interest",
                "public_task", "legitimate_interest")

SCHEMA: dict[str, dict[str, tuple[str, bool]]] = {
    "Contact": {
        **_ENVELOPE,
        "full_name": ("str", True),
        "email": ("str", False),
        "phone": ("str", False),
        "company_ref": ("ref", False),
    },
    "Company": {
        **_ENVELOPE,
        "name": ("str", True),
        "domain": ("str", False),
        "industry": ("str", False),
        "parent_ref": ("ref", False),
    },
    "Deal": {
        **_ENVELOPE,
        "name": ("str", True),
        "amount_minor": ("int", True),
        "currency": ("str", True),
        "stage": ("str", True),
        "company_ref": ("ref", False),
        "pipeline_id": ("uuid", False),
        "close_date": ("time", False),
    },
    "Activity": {
        **_ENVELOPE,
        "kind": ("str", True),
        "occurred_at": ("time", True),
        "subject_ref": ("ref", False),
        "body": ("str", False),
        "source_node_id": ("uuid", False),
    },
    "Ticket": {
        **_ENVELOPE,
        "subject": ("str", True),
        "status": ("str", True),
        "priority": ("str", False),
        "requester_ref": ("ref", False),
    },
    "Invoice": {
        **_ENVELOPE,
        "number": ("str", True),
        "amount_minor": ("int", True),
        "currency": ("str", True),
        "issued_at": ("time", True),
        "deal_ref": ("ref", False),
    },
    "Task": {
        **_ENVELOPE,
        "seat_id": ("uuid", True),
        "required_capabilities": ("list", True),
        "payload": ("dict", True),
        "sla_deadline": ("time", True),
        "state": ("str", True),
        "seat_version": ("int", True),
        "handoff_chain": ("list", False),
    },
    "Seat": {
        **_ENVELOPE,
        "name": ("str", True),
        "version": ("int", True),
        "capability_manifest": ("list", True),
        "permissions_scope": ("dict", True),
        "sla": ("dict", True),
        "fallback_seat_id": ("uuid", False),
        "escalation_ladder": ("list", False),
    },
    "Event": {
        **_ENVELOPE,
        "action": ("str", True),
        "actor": ("str", True),
        "source_node_id": ("uuid", False),
    },
    "Document": {
        **_ENVELOPE,
        "title": ("str", True),
        "mime": ("str", True),
        "uri": ("str", True),
        "owner_ref": ("ref", False),
    },
}

OBJECTS = tuple(SCHEMA)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_KIND_CHECKS = {
    "str": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "num": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
    "uuid": lambda v: isinstance(v, str) and len(v) == 36 and v.count("-") == 4,
    "time": lambda v: isinstance(v, str) and ("T" in v or v.endswith("Z")),
    "ref": lambda v: isinstance(v, str) and ":" in v,
    "list": lambda v: isinstance(v, list),
    "dict": lambda v: isinstance(v, dict),
}


def validate(object_name: str, payload: dict) -> list[str]:
    """Return a list of problems. An empty list means the payload conforms.

    A connector that returns a payload failing this check raises ContractError
    at the canonical boundary, not a data error downstream.
    """
    problems: list[str] = []
    spec = SCHEMA.get(object_name)
    if spec is None:
        return [f"unknown object {object_name!r}; known: {', '.join(OBJECTS)}"]

    for field, (kind, required) in spec.items():
        if field not in payload:
            if required:
                problems.append(f"{object_name}.{field}: required field missing")
            continue
        value = payload[field]
        if value is None:
            if required:
                problems.append(f"{object_name}.{field}: required field is null")
            continue
        if not _KIND_CHECKS[kind](value):
            problems.append(
                f"{object_name}.{field}: expected {kind}, got {type(value).__name__}"
            )

    for field in payload:
        if field not in spec:
            problems.append(f"{object_name}.{field}: field is not in the canonical schema")

    state = payload.get("consent_state")
    if state is not None and state not in CONSENT_STATES:
        problems.append(f"{object_name}.consent_state: {state!r} is not a consent state")

    basis = payload.get("lawful_basis")
    if basis is not None and basis not in LAWFUL_BASES:
        problems.append(f"{object_name}.lawful_basis: {basis!r} is not a lawful basis")

    return problems


def parse_time(value: str) -> datetime:
    """Parse an ISO-8601 timestamp into an aware datetime.

    Timestamps in this system are written at two precisions - seconds by the
    workforce layer, milliseconds by the ledger - and comparing them as strings
    is wrong: "2026-11-14T05:20:44Z" sorts *after* "2026-11-14T05:20:44.582Z"
    because "Z" is greater than ".". Every point-in-time comparison goes through
    here so the two precisions compare as instants. (R-08)
    """
    if not isinstance(value, str):
        raise ValueError(f"expected an ISO-8601 string, got {type(value).__name__}")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def canonical_bytes(payload: dict) -> bytes:
    """Deterministic serialisation: sorted keys, no whitespace, UTF-8.

    Two systems that agree on the payload must produce the same bytes, or the
    hash chain means nothing.
    """
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_hash(payload: dict) -> str:
    """SHA-256 of the canonical serialisation, hex encoded."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def make_ref(object_name: str, record_id: str) -> str:
    """A canonical reference, as stored in a `ref` field."""
    if object_name not in SCHEMA:
        raise ValueError(f"unknown object {object_name!r}")
    return f"{object_name}:{record_id}"


def parse_ref(ref: str) -> tuple[str, str]:
    object_name, _, record_id = ref.partition(":")
    if object_name not in SCHEMA or not record_id:
        raise ValueError(f"malformed canonical reference {ref!r}")
    return object_name, record_id
