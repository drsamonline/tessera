"""Tenant routing.

One process, several customers. Each tenant gets its own `Mesh`, its own
`EventLog` file and its own `Projection`; the router's only job is to pick the
right one from the bearer token and refuse everything else.

The alternative — one mesh with a `tenant_id` column — is the design where a
missing `WHERE` clause becomes a breach. Isolation by construction is cheaper to
audit than isolation by discipline.
"""
from __future__ import annotations

import hmac

from .api import Api, Principal, Request, Response


class TenantRouter:
    """Dispatch a request to the tenant its token belongs to.

    A token is bound to exactly one tenant. There is no cross-tenant token and no
    "admin across all" token, because the first one of those is the one that ends
    up in a support script.
    """

    def __init__(self, apis: dict[str, Api], bindings: dict[str, str]):
        self.apis = apis
        self.bindings = bindings

    def tenant_for(self, token: str) -> str | None:
        if not token:
            return None
        found = None
        for candidate, tenant in self.bindings.items():
            if hmac.compare_digest(candidate, token):
                found = tenant
        return found

    def handle(self, request: Request) -> Response:
        header = request.headers.get("Authorization") or request.headers.get("authorization") or ""
        token = header[7:] if header.lower().startswith("bearer ") else ""
        tenant = self.tenant_for(token)
        if tenant is None:
            return Response(401, {"error": "unauthenticated"})
        api = self.apis.get(tenant)
        if api is None:
            # A token bound to a tenant with no runtime is a configuration error,
            # and saying so is better than a 401 that sends someone to their token.
            return Response(503, {"error": "tenant_not_running", "tenant": tenant})
        return api.handle(request)

    def health(self) -> dict:
        return {"status": "ok", "tenants": sorted(self.apis),
                "tokens": len(self.bindings)}


def multi_tenant_api(tenant_ids: list[str], tokens: dict[str, tuple[str, Principal]],
                     build) -> TenantRouter:
    """`build(tenant_id, tokens_for_that_tenant) -> Api`.

    The inner `Api` still authenticates its own token. That is deliberate: the
    router decides *which* tenant, and the tenant's own API decides *what* the
    caller may do. Two checks, two questions, and neither is a substitute for the
    other.
    """
    by_tenant: dict[str, list[str]] = {}
    for token, (tenant, _principal) in tokens.items():
        by_tenant.setdefault(tenant, []).append(token)

    apis, bindings = {}, {}
    for tenant in tenant_ids:
        apis[tenant] = build(tenant, by_tenant.get(tenant, []))
    for token, (tenant, _principal) in tokens.items():
        if tenant not in apis:
            raise ValueError(f"token bound to unknown tenant {tenant!r}")
        bindings[token] = tenant
    return TenantRouter(apis, bindings)
