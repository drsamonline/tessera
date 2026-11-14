"""Zendesk connector, Support API v2.

Endpoint shapes, the `meta.after_cursor` pagination and the `user` wrapper on a
create response are from the public Zendesk Support API documentation. They have
**not** been exercised against a live subdomain: every test drives the connector
through a recorded transport that speaks these shapes.

Zendesk has two behaviours worth naming:

* a create returns `{"user": {...}}`, not the record;
* pagination is cursor-based through `page[after]` and reports `meta.has_more`.
"""

from __future__ import annotations

from .base import ProviderConnector
from ..connector import ContractError, Health


class ZendeskConnector(ProviderConnector):
    provider = "zendesk"
    objects = ("Contact", "Ticket")
    RATE_PER_MINUTE = 400
    COST_PER_CALL = 0.0

    field_map = {
        "Contact": {
            "email": "email",
            "phone": "phone",
            "full_name": "name",
        },
        "Ticket": {
            "subject": "subject",
            "status": "status",
            "priority": "priority",
        },
    }

    _PATHS = {"Contact": "/api/v2/users", "Ticket": "/api/v2/tickets"}

    def __init__(self, node_id: str, transport, tenant_id: str, token: str = "",
                 base_url: str = "https://example.zendesk.com", page_size: int = 2,
                 policy: dict | None = None, identity_path: str | None = None):
        super().__init__(node_id, transport, tenant_id, base_url, page_size, policy,
                         identity_path=identity_path)
        self.token = token
        self.category = "support"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    # -- read -------------------------------------------------------------
    def _fetch_page(self, object_name: str, cursor: str | None):
        self._require(object_name)
        params = {"page[size]": self.page_size}
        if cursor:
            params["page[after]"] = cursor
        response = self.transport.request(
            "GET", self._url(self._PATHS[object_name]),
            headers=self._headers(), params=params,
        )
        body = response.json() or {}
        key = "users" if object_name == "Contact" else "tickets"
        rows = body.get(key, [])
        meta = body.get("meta") or {}
        next_cursor = meta.get("after_cursor") if meta.get("has_more") else None
        return rows, next_cursor

    def _to_canonical(self, object_name: str, row: dict) -> dict:
        stamp = row.get("updated_at") or row.get("created_at")
        record = self._envelope(row.get("id", ""), stamp)
        for canonical_name, provider_name in self.field_map[object_name].items():
            if isinstance(provider_name, str) and provider_name in row:
                record[canonical_name] = row[provider_name]
        return record

    # -- write ------------------------------------------------------------
    def _to_provider(self, object_name: str, payload: dict) -> dict:
        body = {}
        for canonical_name, provider_name in self.field_map[object_name].items():
            if canonical_name in payload and isinstance(provider_name, str):
                body[provider_name] = payload[canonical_name]
        return body

    def _create(self, object_name: str, body: dict) -> str:
        response = self.transport.request(
            "POST", self._url(self._PATHS[object_name]), headers=self._headers(),
            json_body=body,
        )
        data = response.json() or {}
        key = "user" if object_name == "Contact" else "ticket"
        record = data.get(key) or data
        if not record.get("id"):
            raise ContractError("Zendesk create returned no id")
        return str(record["id"])

    def _update(self, object_name: str, external_id: str, body: dict) -> None:
        self.transport.request(
            "PUT", self._url(f"{self._PATHS[object_name]}/{external_id}"),
            headers=self._headers(), json_body=body,
        )

    def health(self):
        try:
            self.transport.request(
                "GET", self._url("/api/v2/users/me"), headers=self._headers()
            )
        except Exception as exc:  # noqa: BLE001
            return Health(status="offline", detail=type(exc).__name__)
        return Health(status="online")
