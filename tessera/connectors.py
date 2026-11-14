"""Two connectors, and one deliberately broken one.

    NativeConnector   the reference implementation of the contract, backed by a
                      dictionary. This is what the native CRM node looks like at
                      the contract level.
    SimulatedConnector a deterministic stand-in for an external SaaS node: same
                      contract, injected latency and failure modes, no network.
    BrokenConnector   violates one rule per mode. It exists so the conformance
                      suite can be shown to reject what it should reject. A
                      suite that only ever passes is a rubber stamp.

HubSpot, Salesforce and Zendesk connectors are specified and not written. A real
connector is this class plus an HTTP client; the contract does not change.
"""

from __future__ import annotations

import itertools
from typing import Callable

from . import canonical
from .connector import (
    AuthError, Capability, Connector, ContractError, Health, RateLimit,
    RateLimited, ReadResult, SchemaDrift, TransientError, WriteResult,
)


class _StoreConnector(Connector):
    """Shared dictionary-backed behaviour."""

    def __init__(self, node_id: str, category: str, objects: tuple[str, ...],
                 page_size: int = 2):
        self.node_id = node_id
        self.category = category
        self._objects = objects
        self._page_size = page_size
        self._records: dict[str, dict[str, dict]] = {o: {} for o in objects}
        self._idempotency: dict[str, str] = {}
        self._seq = itertools.count(1)

    # -- contract ---------------------------------------------------------
    def capabilities(self) -> Capability:
        return Capability(objects=self._objects, operations=("read", "write"),
                          categories=(self.category,))

    def schema(self) -> dict:
        """Identity map: this node uses canonical names directly."""
        out = {}
        for obj in self._objects:
            out[obj] = {field: field for field in canonical.SCHEMA[obj]}
        return out

    def read(self, object_name: str, cursor: str | None = None) -> ReadResult:
        if object_name not in self._records:
            raise SchemaDrift(f"{self.node_id} does not carry {object_name}")
        rows = list(self._records[object_name].values())
        start = int(cursor) if cursor else 0
        page = rows[start:start + self._page_size]
        nxt = str(start + self._page_size) if start + self._page_size < len(rows) else None
        return ReadResult(records=page, cursor=nxt)

    def write(self, object_name: str, payload: dict, idempotency_key: str) -> WriteResult:
        if object_name not in self._records:
            raise SchemaDrift(f"{self.node_id} does not carry {object_name}")
        if idempotency_key in self._idempotency:
            return WriteResult(ok=True, external_id=self._idempotency[idempotency_key])
        problems = canonical.validate(object_name, payload)
        if problems:
            raise ContractError("; ".join(problems[:3]))
        external_id = payload.get("id") or canonical.uuid7()
        stored = dict(payload, id=external_id)
        self._records[object_name][external_id] = stored
        self._idempotency[idempotency_key] = external_id
        return WriteResult(ok=True, external_id=external_id)

    def health(self) -> Health:
        return Health(status="online")

    def rate_limit(self) -> RateLimit:
        return RateLimit(requests_per_minute=600, burst=10)

    def cost_estimate(self, operation: str, count: int = 1) -> float:
        return 0.001 * count

    # -- test helpers -----------------------------------------------------
    def seed(self, object_name: str, payload: dict) -> str:
        problems = canonical.validate(object_name, payload)
        if problems:
            raise ContractError("; ".join(problems[:3]))
        self._records[object_name][payload["id"]] = dict(payload)
        return payload["id"]

    def count(self, object_name: str) -> int:
        return len(self._records[object_name])


class NativeConnector(_StoreConnector):
    """The native node: canonical names, no mapping, no surprises."""

    def __init__(self, node_id: str = "native", page_size: int = 2):
        super().__init__(node_id, "custom", canonical.OBJECTS, page_size)

    def cost_estimate(self, operation: str, count: int = 1) -> float:
        return 0.0


class SimulatedConnector(_StoreConnector):
    """An external node, deterministically misbehaving on request.

    `fail_times` makes the next N reads raise TransientError. `throttle_times`
    makes them raise RateLimited. `drift` makes read() raise SchemaDrift. These
    exist to exercise the retry wrapper and the breaker without a network.
    """

    def __init__(self, node_id: str, category: str = "sales",
                 objects: tuple[str, ...] = ("Contact", "Company", "Activity"),
                 page_size: int = 2):
        super().__init__(node_id, category, objects, page_size)
        self.fail_times = 0
        self.throttle_times = 0
        self.drift = False
        self.calls = 0

    def read(self, object_name: str, cursor: str | None = None) -> ReadResult:
        self.calls += 1
        if self.drift:
            raise SchemaDrift(f"{self.node_id} lost the field map for {object_name}")
        if self.throttle_times > 0:
            self.throttle_times -= 1
            raise RateLimited(f"{self.node_id} is throttling", retry_after=0.0)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise TransientError(f"{self.node_id} timed out")
        return super().read(object_name, cursor)

    def health(self) -> Health:
        if self.fail_times > 0:
            return Health(status="degraded", detail="recent transient failures")
        return Health(status="online")


class BrokenConnector(Connector):
    """One violation per mode, so the conformance suite can be tested against it.

    Modes: no_capabilities, bad_schema, bad_record, no_pagination,
    non_idempotent_write, bad_health, no_rate_limit, negative_cost, wrong_error.
    """

    def __init__(self, mode: str, node_id: str = "broken"):
        self.mode = mode
        self.node_id = node_id
        self.category = "sales"
        self._writes: list[str] = []

    def capabilities(self):
        if self.mode == "no_capabilities":
            return None
        return Capability(objects=("Contact",), operations=("read", "write"))

    def schema(self):
        if self.mode == "bad_schema":
            return {"Contact": {"not_a_canonical_field": "whatever"}}
        return {"Contact": {f: f for f in canonical.SCHEMA["Contact"]}}

    def read(self, object_name: str, cursor: str | None = None) -> ReadResult:
        if self.mode == "bad_record":
            return ReadResult(records=[{"id": "not-a-uuid"}])
        if self.mode == "no_pagination":
            return ReadResult(records=[], cursor="always-more")
        if self.mode == "wrong_error":
            raise ValueError("not from the taxonomy")
        return ReadResult(records=[], cursor=None)

    def write(self, object_name: str, payload: dict, idempotency_key: str) -> WriteResult:
        if self.mode == "non_idempotent_write":
            self._writes.append(idempotency_key)
            return WriteResult(ok=True, external_id=f"row-{len(self._writes)}")
        return WriteResult(ok=True, external_id="row-1")

    def health(self):
        if self.mode == "bad_health":
            return Health.__new__(Health)  # bypasses __post_init__
        return Health(status="online")

    def rate_limit(self):
        if self.mode == "no_rate_limit":
            return RateLimit(requests_per_minute=0)
        return RateLimit(requests_per_minute=60)

    def cost_estimate(self, operation: str, count: int = 1) -> float:
        if self.mode == "negative_cost":
            return -1.0
        return 0.0

    def subscribe(self) -> None:
        raise NotImplementedError("subscribe() is not implemented in the reference core")
