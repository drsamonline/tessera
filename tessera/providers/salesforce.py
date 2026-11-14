"""Salesforce connector, REST API v60.0.

SOQL field names, the `/services/data/v60.0/sobjects/...` write endpoints and the
`nextRecordsUrl` cursor are from the public Salesforce REST documentation. They
have **not** been exercised against a live org: every test drives the connector
through a recorded transport that speaks these shapes.

Two Salesforce behaviours the other two providers do not have, both handled here:

* a query returns `done` and, when false, a `nextRecordsUrl` that replaces the
  whole request rather than extending it;
* every record carries an `attributes` block that is not data.
"""

from __future__ import annotations

from .base import ProviderConnector
from ..connector import ContractError, Health

API_VERSION = "v60.0"


class SalesforceConnector(ProviderConnector):
    provider = "salesforce"
    objects = ("Contact", "Company", "Deal")
    RATE_PER_MINUTE = 100
    COST_PER_CALL = 0.0

    field_map = {
        "Contact": {
            "email": "Email",
            "phone": "Phone",
            "full_name": "Name",
        },
        "Company": {
            "name": "Name",
            "domain": "Website",
            "industry": "Industry",
        },
        "Deal": {
            "name": "Name",
            "amount_minor": "Amount",
            "stage": "StageName",
            "currency": "CurrencyIsoCode",
        },
    }

    _SOBJECTS = {"Contact": "Contact", "Company": "Account", "Deal": "Opportunity"}

    def __init__(self, node_id: str, transport, tenant_id: str, token: str = "",
                 base_url: str = "https://example.my.salesforce.com", page_size: int = 2,
                 policy: dict | None = None):
        super().__init__(node_id, transport, tenant_id, base_url, page_size, policy)
        self.token = token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    # -- read -------------------------------------------------------------
    def _query_for(self, object_name: str) -> str:
        fields = ["Id", "LastModifiedDate"]
        for provider_name in self.field_map[object_name].values():
            if isinstance(provider_name, str) and provider_name not in fields:
                fields.append(provider_name)
        return f"SELECT {', '.join(fields)} FROM {self._SOBJECTS[object_name]}"

    def _fetch_page(self, object_name: str, cursor: str | None):
        self._require(object_name)
        if cursor:
            # Salesforce hands back a full path; it is the next request.
            response = self.transport.request(
                "GET", self._url(cursor), headers=self._headers()
            )
        else:
            response = self.transport.request(
                "GET", self._url(f"/services/data/{API_VERSION}/query"),
                headers=self._headers(), params={"q": self._query_for(object_name)},
            )
        body = response.json() or {}
        rows = body.get("records", [])
        next_cursor = None if body.get("done", True) else body.get("nextRecordsUrl")
        return rows, next_cursor

    def _to_canonical(self, object_name: str, row: dict) -> dict:
        record = self._envelope(row.get("Id", ""), row.get("LastModifiedDate"))
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
            "POST", self._url(f"/services/data/{API_VERSION}/sobjects/{self._SOBJECTS[object_name]}"),
            headers=self._headers(), json_body=body,
        )
        data = response.json() or {}
        if not data.get("id"):
            raise ContractError("Salesforce create returned no id")
        return str(data["id"])

    def _update(self, object_name: str, external_id: str, body: dict) -> None:
        self.transport.request(
            "PATCH",
            self._url(f"/services/data/{API_VERSION}/sobjects/{self._SOBJECTS[object_name]}/{external_id}"),
            headers=self._headers(), json_body=body,
        )

    def health(self):
        try:
            self.transport.request(
                "GET", self._url(f"/services/data/{API_VERSION}/limits"),
                headers=self._headers(),
            )
        except Exception as exc:  # noqa: BLE001
            return Health(status="offline", detail=type(exc).__name__)
        return Health(status="online")
