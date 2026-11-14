"""HubSpot connector, CRM v3.

Field names, endpoint shapes and the `paging.next.after` cursor are from the
public HubSpot CRM v3 documentation. They have **not** been exercised against a
live tenant: every test in this repository drives the connector through a
recorded transport that speaks these shapes. Treat the mapping as a starting
point that a real tenant will correct, not as a verified integration.
"""

from __future__ import annotations

from .base import ProviderConnector
from ..connector import ContractError
from ..transport import Response


class HubSpotConnector(ProviderConnector):
    provider = "hubspot"
    objects = ("Contact", "Company", "Deal")
    RATE_PER_MINUTE = 100
    COST_PER_CALL = 0.0

    field_map = {
        "Contact": {
            "email": "email",
            "phone": "phone",
            "full_name": ("firstname", "lastname"),
        },
        "Company": {
            "name": "name",
            "domain": "domain",
            "industry": "industry",
        },
        "Deal": {
            "name": "dealname",
            "amount_minor": "amount",
            "stage": "dealstage",
            "currency": "deal_currency_code",
        },
    }

    _PATHS = {
        "Contact": "/crm/v3/objects/contacts",
        "Company": "/crm/v3/objects/companies",
        "Deal": "/crm/v3/objects/deals",
    }

    def __init__(self, node_id: str, transport, tenant_id: str, token: str = "",
                 base_url: str = "https://api.hubapi.com", page_size: int = 2,
                 policy: dict | None = None):
        super().__init__(node_id, transport, tenant_id, base_url, page_size, policy)
        self.token = token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    # -- read -------------------------------------------------------------
    def _fetch_page(self, object_name: str, cursor: str | None):
        self._require(object_name)
        params = {"limit": self.page_size}
        if cursor:
            params["after"] = cursor
        if object_name == "Contact":
            params["properties"] = "email,firstname,lastname,phone"
        response = self.transport.request(
            "GET", self._url(self._PATHS[object_name]),
            headers=self._headers(), params=params,
        )
        body = response.json() or {}
        rows = body.get("results", [])
        paging = (body.get("paging") or {}).get("next") or {}
        return rows, paging.get("after")

    def _to_canonical(self, object_name: str, row: dict) -> dict:
        props = row.get("properties") or {}
        record = self._envelope(row.get("id", ""), row.get("updatedAt"))
        for canonical_name, provider_name in self.field_map[object_name].items():
            if isinstance(provider_name, str) and provider_name in props:
                record[canonical_name] = props[provider_name]
        if object_name == "Contact":
            name = " ".join(
                part for part in (props.get("firstname"), props.get("lastname")) if part
            ).strip()
            if name:
                record["full_name"] = name
        return record

    # -- write ------------------------------------------------------------
    def _to_provider(self, object_name: str, payload: dict) -> dict:
        props = {}
        for canonical_name, provider_name in self.field_map[object_name].items():
            if canonical_name not in payload:
                continue
            if isinstance(provider_name, str):
                props[provider_name] = payload[canonical_name]
        if object_name == "Contact" and payload.get("full_name"):
            first, _, last = str(payload["full_name"]).partition(" ")
            props["firstname"] = first
            props["lastname"] = last
        return {"properties": props}

    def _create(self, object_name: str, body: dict) -> str:
        response = self.transport.request(
            "POST", self._url(self._PATHS[object_name]), headers=self._headers(),
            json_body=body,
        )
        data = response.json() or {}
        if "id" not in data:
            raise ContractError("HubSpot create returned no id")
        return str(data["id"])

    def _update(self, object_name: str, external_id: str, body: dict) -> None:
        self.transport.request(
            "PATCH", self._url(f"{self._PATHS[object_name]}/{external_id}"),
            headers=self._headers(), json_body=body,
        )

    # -- health -----------------------------------------------------------
    def health(self):
        try:
            self.transport.request(
                "GET", self._url(self._PATHS["Contact"]),
                headers=self._headers(), params={"limit": 1},
            )
        except ContractError:
            return super().health()
        except Exception as exc:  # noqa: BLE001
            from ..connector import Health
            return Health(status="offline", detail=type(exc).__name__)
        from ..connector import Health
        return Health(status="online")
