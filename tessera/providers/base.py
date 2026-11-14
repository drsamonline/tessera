"""Shared behaviour for a real provider connector.

A provider connector is three things the base class does not do:

    1. field mapping      canonical name <-> the provider's name
    2. envelope synthesis the canonical fields a provider has never heard of
    3. pagination         the provider's cursor shape

Everything else - idempotency, the identity map, error propagation, the
contract - is here, so three connectors cannot drift apart in behaviour.

The envelope is a real design decision, recorded rather than assumed:

* `id` is derived from the provider's identifier through a UUIDv5 in a namespace
  scoped to the node, and remembered in an identity map once the record has been
  written through the mesh. The external identifier never becomes the canonical
  identifier: that way a node can be replaced without rewriting history.
* `tenant_id`, `consent_state`, `lawful_basis`, `purpose_id` and
  `retention_policy_id` are **tenant policy, not provider data**. A CRM does not
  know your lawful basis. The connector is configured with them and stamps every
  record, and the mesh records that they were stamped rather than observed.
* `valid_from` and `tx_time` come from the provider's own modified timestamp
  where it has one, and from the read time where it does not.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .. import canonical
from ..connector import (
    Capability, Connector, ContractError, Health, RateLimit, ReadResult, SchemaDrift,
    WriteResult,
)
from ..transport import Transport

NAMESPACE = uuid.UUID("6f2b1d8e-3c4a-4b9e-9d2f-0a1c5e7b8d90")

DEFAULT_POLICY = {
    "consent_state": "pending",
    "lawful_basis": "legitimate_interest",
    "purpose_id": "crm-federation",
    "retention_policy_id": "default-24m",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class ProviderConnector(Connector):
    provider = "generic"
    objects: tuple[str, ...] = ("Contact",)
    field_map: dict[str, dict[str, str]] = {}

    def __init__(self, node_id: str, transport: Transport, tenant_id: str,
                 base_url: str = "", page_size: int = 2,
                 policy: dict | None = None, category: str = "sales"):
        self.node_id = node_id
        self.category = category
        self.transport = transport
        self.tenant_id = tenant_id
        self.base_url = base_url.rstrip("/")
        self.page_size = page_size
        self.policy = dict(DEFAULT_POLICY, **(policy or {}))
        self._identity: dict[str, str] = {}      # external id -> canonical id
        self._reverse: dict[str, str] = {}       # canonical id -> external id
        self._idempotency: dict[str, str] = {}   # key -> external id

    # -- identity ---------------------------------------------------------
    def canonical_id(self, external_id: str) -> str:
        """Stable across reads, and remembered once the mesh has written the record."""
        external_id = str(external_id)
        if external_id in self._identity:
            return self._identity[external_id]
        derived = str(uuid.uuid5(NAMESPACE, f"{self.node_id}:{external_id}"))
        self._identity[external_id] = derived
        return derived

    def external_id(self, canonical_id: str) -> str | None:
        return self._reverse.get(canonical_id)

    def _remember(self, external_id: str, canonical_id: str) -> None:
        self._identity[str(external_id)] = canonical_id
        self._reverse[canonical_id] = str(external_id)

    def _envelope(self, external_id: str, updated_at: str | None = None) -> dict:
        stamp = updated_at or _now_iso()
        return {
            "id": self.canonical_id(external_id),
            "tenant_id": self.tenant_id,
            "valid_from": stamp,
            "tx_time": _now_iso(),
            "consent_state": self.policy["consent_state"],
            "lawful_basis": self.policy["lawful_basis"],
            "purpose_id": self.policy["purpose_id"],
            "retention_policy_id": self.policy["retention_policy_id"],
        }

    # -- contract ---------------------------------------------------------
    def capabilities(self) -> Capability:
        return Capability(objects=self.objects, operations=("read", "write"),
                          categories=(self.category,))

    def schema(self) -> dict:
        return {obj: dict(self.field_map.get(obj, {})) for obj in self.objects}

    def read(self, object_name: str, cursor: str | None = None) -> ReadResult:
        self._require(object_name)
        rows, next_cursor = self._fetch_page(object_name, cursor)
        records = [self._to_canonical(object_name, row) for row in rows]
        return ReadResult(records=records, cursor=next_cursor)

    def write(self, object_name: str, payload: dict, idempotency_key: str) -> WriteResult:
        self._require(object_name)
        if idempotency_key in self._idempotency:
            return WriteResult(ok=True, external_id=self._idempotency[idempotency_key])

        problems = canonical.validate(object_name, payload)
        if problems:
            raise ContractError("; ".join(problems[:3]))

        body = self._to_provider(object_name, payload)
        external = self._external_id_of(payload)
        if external:
            self._update(object_name, external, body)
        else:
            external = self._create(object_name, body)

        self._remember(external, payload["id"])
        self._idempotency[idempotency_key] = str(external)
        return WriteResult(ok=True, external_id=str(external))

    def health(self) -> Health:
        try:
            self._fetch_page(self.objects[0], None)
        except ContractError:
            return Health(status="degraded", detail="the node rejected a probe request")
        except Exception as exc:  # noqa: BLE001 - a health check reports, never raises
            return Health(status="offline", detail=type(exc).__name__)
        return Health(status="online")

    def rate_limit(self) -> RateLimit:
        return RateLimit(requests_per_minute=self.RATE_PER_MINUTE, burst=5)

    def cost_estimate(self, operation: str, count: int = 1) -> float:
        return self.COST_PER_CALL * max(1, count)

    # -- hooks a provider fills in ---------------------------------------
    RATE_PER_MINUTE = 100
    COST_PER_CALL = 0.0

    def _fetch_page(self, object_name: str, cursor: str | None) -> tuple[list[dict], str | None]:
        raise NotImplementedError

    def _to_canonical(self, object_name: str, row: dict) -> dict:
        raise NotImplementedError

    def _to_provider(self, object_name: str, payload: dict) -> dict:
        raise NotImplementedError

    def _create(self, object_name: str, body: dict) -> str:
        raise NotImplementedError

    def _update(self, object_name: str, external_id: str, body: dict) -> None:
        raise NotImplementedError

    # -- helpers ----------------------------------------------------------
    def _require(self, object_name: str) -> None:
        if object_name not in self.objects:
            raise SchemaDrift(f"{self.node_id} does not carry {object_name}")

    def _external_id_of(self, payload: dict) -> str | None:
        return self._reverse.get(payload.get("id", ""))

    def _headers(self) -> dict:
        return {}

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"
