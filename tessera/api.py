"""The HTTP surface: a JSON API over the reference core.

Deliverable 18 asks for an OpenAPI document and an MCP discovery schema. Both are
generated from the route table here, so a route cannot exist without appearing in
the contract.

Deliberately stdlib: `http.server` and nothing else. The point of this module is
to make the core reachable, not to be a production gateway. What it does have is
the part that matters for an audit trail:

    every request names a principal
    every scope is checked before the handler runs
    every mutation writes a ledger event naming the caller

The last one is not decoration. The domain logs a system actor for a sync and a
human actor for a write; the API layer records *which caller* asked for it, which
is the question an incident review actually asks.
"""

from __future__ import annotations

import hmac
import json
import re
from dataclasses import dataclass, field

from . import access, canonical

SCOPES = ("read", "write", "workforce", "audit", "admin")


@dataclass
class Principal:
    """A caller. `scopes` gate the route; `role` gates the data.

    Both are needed and they answer different questions. A scope says "may this
    caller reach the endpoint"; a role says "may this caller see this field of
    this record". Collapsing them is how a read scope ends up granting access to
    every column in the tenant.
    """
    id: str
    scopes: tuple[str, ...] = ("read",)
    role: str = "auditor"
    seat_id: str | None = None
    # "human" or "agent". The audit trail records who acted; defaulting every
    # caller to "human" made an agent's action indistinguishable from a person's. (R-11)
    kind: str = "human"

    def can(self, scope: str) -> bool:
        return "admin" in self.scopes or scope in self.scopes


@dataclass
class Request:
    method: str
    path: str
    query: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    body: dict | None = None


@dataclass
class Response:
    status: int
    body: dict


class Api:
    """Route table plus auth plus audit. One object, no framework."""

    def __init__(self, tenant_id: str, tokens: dict[str, Principal], log=None,
                 mesh=None, projection=None, workforce=None, policy=None):
        self.tenant_id = tenant_id
        self.policy = policy or access.DEFAULT_POLICY
        self.tokens = tokens
        self.log = log
        self.mesh = mesh
        self.projection = projection
        self.workforce = workforce
        self.routes = self._routes()

    # -- routing ----------------------------------------------------------
    def _routes(self):
        return [
            ("GET", r"^/health$", None, self._health),
            ("GET", r"^/v1/objects/(?P<object>[A-Za-z]+)$", "read", self._list),
            ("GET", r"^/v1/objects/(?P<object>[A-Za-z]+)/export$", "read", self._export),
            ("GET", r"^/v1/objects/(?P<object>[A-Za-z]+)/(?P<id>[0-9a-f\-]{36})$",
             "read", self._get),
            ("GET", r"^/v1/objects/(?P<object>[A-Za-z]+)/(?P<id>[0-9a-f\-]{36})/history$",
             "read", self._history),
            ("GET", r"^/v1/objects/(?P<object>[A-Za-z]+)/(?P<id>[0-9a-f\-]{36})/as-of$",
             "read", self._as_of),
            ("GET", r"^/v1/mesh/view/(?P<object>[A-Za-z]+)/(?P<id>[0-9a-f\-]{36})$",
             "read", self._unified),
            ("POST", r"^/v1/objects/(?P<object>[A-Za-z]+)/(?P<id>[0-9a-f\-]{36})"
                     r"/fields/(?P<field_name>[A-Za-z_]+)$", "write", self._write_field),
            ("POST", r"^/v1/tasks$", "workforce", self._assign),
            ("POST", r"^/v1/tasks/(?P<id>[0-9a-f\-]{36})/escalate$", "workforce", self._escalate),
            ("GET", r"^/v1/audit/verify$", "audit", self._verify),
        ]

    # -- entry point ------------------------------------------------------
    def handle(self, request: Request) -> Response:
        try:
            return self._dispatch(request)
        except Exception as exc:  # noqa: BLE001 - a surface must answer, always
            return Response(500, {"error": type(exc).__name__, "detail": str(exc)})

    def _dispatch(self, request: Request) -> Response:
        for method, pattern, scope, handler in self.routes:
            match = re.match(pattern, request.path)
            if not match:
                continue
            if method != request.method:
                continue

            if scope is not None:
                principal, failure = self._authenticate(request, scope)
                if failure:
                    return failure
                request.query["_principal"] = principal

            result = handler(request, **match.groupdict())
            if request.method == "POST" and scope is not None:
                self._audit(request, request.query["_principal"])
            return result
        return Response(404, {"error": "not_found", "path": request.path})

    def _authenticate(self, request: Request, scope: str):
        header = request.headers.get("Authorization") or request.headers.get("authorization") or ""
        token = header[7:] if header.lower().startswith("bearer ") else ""
        principal = self._principal_for(token)
        if principal is None:
            return None, Response(401, {"error": "unauthenticated"})
        if not principal.can(scope):
            return principal, Response(403, {"error": "forbidden", "scope": scope})
        return principal, None

    def _principal_for(self, token: str) -> Principal | None:
        """Compare every token in constant time.

        A dict lookup returns early on the first differing byte, which is a timing
        signal. It is a weak one and this is a development surface, but a token
        comparison is not the place to be relaxed about it.
        """
        if not token:
            return None
        found = None
        for candidate, principal in self.tokens.items():
            if hmac.compare_digest(candidate, token):
                found = principal
        return found

    def _audit(self, request: Request, principal: Principal) -> None:
        if not self.log:
            return
        self.log.append(
            self.tenant_id, principal.kind if principal.kind in ("human", "agent") else "system",
            "api.call",
            {"route": request.path, "method": request.method,
             "principal": principal.id,
             "body_hash": canonical.canonical_hash(request.body or {})},
            source_node_id="api",
        )

    # -- handlers ---------------------------------------------------------
    def _health(self, request: Request) -> Response:
        return Response(200, {"status": "ok", "tenant": self.tenant_id,
                              "auth_required": True})

    def _store(self):
        if self.projection is None:
            raise RuntimeError("no projection is attached to this API")
        return self.projection.state

    def _list(self, request: Request, object: str) -> Response:
        if object not in canonical.SCHEMA:
            return Response(404, {"error": "unknown_object", "object": object})
        principal = request.query["_principal"]
        if not self.policy.can_touch_object(principal, object):
            return Response(403, {"error": "forbidden_object", "object": object})
        visible = self.policy.filter_rows(principal, object, self._store().get(object, {}))
        return Response(200, {"object": object, "ids": sorted(visible)})

    def _export(self, request: Request, object: str) -> Response:
        """The export path, redacted by the same gate as the read path.

        An export that forgets the policy is the classic leak: the screen hides a
        column and the CSV does not.
        """
        if object not in canonical.SCHEMA:
            return Response(404, {"error": "unknown_object", "object": object})
        principal = request.query["_principal"]
        if not self.policy.can_touch_object(principal, object):
            return Response(403, {"error": "forbidden_object", "object": object})
        visible = self.policy.filter_rows(principal, object, self._store().get(object, {}))
        return Response(200, {"object": object, "count": len(visible),
                              "records": [visible[key] for key in sorted(visible)]})

    def _get(self, request: Request, object: str, id: str) -> Response:
        principal = request.query["_principal"]
        record = self._store().get(object, {}).get(id)
        if record is None:
            return Response(404, {"error": "not_found"})
        try:
            visible = self.policy.redact_or_deny(principal, object, record)
        except access.AccessDenied:
            return Response(404, {"error": "not_found"})
        return Response(200, {"object": object, "id": id, "record": visible})

    def _history(self, request: Request, object: str, id: str) -> Response:
        if not self.log:
            return Response(503, {"error": "no_ledger"})
        principal = request.query["_principal"]
        denied = self.policy.denied_fields(principal, object)
        ref = canonical.make_ref(object, id)
        rows = self.log.history(self.tenant_id, ref)
        events = []
        for r in rows:
            payload = r.get("payload") or {}
            # history carries records too; a denied field must not leak through it
            if isinstance(payload.get("record"), dict):
                payload = dict(payload, record={
                    k: v for k, v in payload["record"].items() if k not in denied})
            events.append({"sequence": r["sequence"], "timestamp": r["timestamp"],
                           "actor": r["actor"], "action": r["action"],
                           "hash": r["hash"], "payload": payload})
        return Response(200, {"object": object, "id": id, "events": events})

    def _as_of(self, request: Request, object: str, id: str) -> Response:
        at = request.query.get("at")
        if not at:
            return Response(400, {"error": "missing_parameter", "parameter": "at"})
        if self.projection is None:
            return Response(503, {"error": "no_projection"})
        principal = request.query["_principal"]
        record = self.projection.as_of(object, id, at)
        return Response(200, {"object": object, "id": id, "at": at,
                              "record": self.policy.redact(principal, object, record)})

    def _unified(self, request: Request, object: str, id: str) -> Response:
        if self.mesh is None:
            return Response(503, {"error": "no_mesh"})
        try:
            view = self.mesh.unified_view(object, id)
        except KeyError:
            return Response(404, {"error": "not_found"})
        principal = request.query["_principal"]
        hidden = {name for name in view["fields"]
                  if not self.policy.can_read_field(principal, object, name)}
        if hidden:
            view = dict(view)
            view["fields"] = {k: v for k, v in view["fields"].items() if k not in hidden}
            view["conflicts"] = [c for c in view.get("conflicts", [])
                                 if c.get("field") not in hidden]
        return Response(200, view)

    def _write_field(self, request: Request, object: str, id: str, field_name: str) -> Response:
        if self.mesh is None:
            return Response(503, {"error": "no_mesh"})
        body = request.body or {}
        if "value" not in body:
            return Response(400, {"error": "missing_field", "field": "value"})
        principal = request.query["_principal"]
        if not self.policy.can_edit_field(principal, object, field_name):
            return Response(403, {"error": "forbidden_field", "field": field_name})
        try:
            result = self.mesh.write_field(object, id, field_name, body["value"],
                                           actor="human")
        except PermissionError as exc:
            return Response(403, {"error": "not_writable", "detail": str(exc)})
        except KeyError:
            return Response(404, {"error": "not_found"})
        except ValueError as exc:
            return Response(422, {"error": "invalid_record", "detail": str(exc)})
        return Response(200, dict(result, principal=principal.id))

    def _assign(self, request: Request, **_) -> Response:
        if self.workforce is None:
            return Response(503, {"error": "no_workforce"})
        body = request.body or {}
        seat_id = body.get("seat_id")
        if not seat_id:
            return Response(400, {"error": "missing_field", "field": "seat_id"})
        from .workforce import Task
        task = Task(id=body.get("id") or canonical.uuid7(), seat_id=seat_id,
                    required_capabilities=list(body.get("required_capabilities", [])),
                    payload=dict(body.get("payload", {})))
        try:
            decision = self.workforce.assign(task)
        except Exception as exc:  # noqa: BLE001
            return Response(409, {"error": "cannot_assign", "detail": str(exc)})
        return Response(201, {"task": task.id, "occupant": decision["id"],
                              "score": decision["score"],
                              "weights_version": decision["weights_version"]})

    def _escalate(self, request: Request, id: str) -> Response:
        if self.workforce is None:
            return Response(503, {"error": "no_workforce"})
        body = request.body or {}
        trigger = body.get("trigger")
        if not trigger:
            return Response(400, {"error": "missing_field", "field": "trigger"})
        try:
            packet = self.workforce.escalate(id, trigger,
                                             evidence=body.get("evidence"))
        except Exception as exc:  # noqa: BLE001
            return Response(409, {"error": "cannot_escalate", "detail": str(exc)})
        return Response(201, {"packet": packet.id, "from": packet.from_seat,
                              "to": packet.to_seat, "signature": packet.signature})

    def _verify(self, request: Request) -> Response:
        if not self.log:
            return Response(503, {"error": "no_ledger"})
        ok, problems = self.log.verify()
        body = {"chain_ok": ok, "problems": problems}
        if self.projection is not None:
            body["rebuildable"] = self.projection.verify_rebuildable()["rebuildable"]
        return Response(200 if ok else 409, body)


# ---------------------------------------------------------------------------
# A runnable server, for a human poking at it
# ---------------------------------------------------------------------------

def handler_for(api: Api):
    """The request handler class for an Api.

    Separate from `serve` so a test can bind a server to port 0 and make a real
    HTTP request against it. A server that is only testable through its own
    process is a server nobody tests.
    """
    from http.server import BaseHTTPRequestHandler
    from urllib.parse import parse_qs, urlparse

    class Handler(BaseHTTPRequestHandler):
        def _handle(self, method):
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                body = None
            request = Request(method=method, path=parsed.path,
                              query={k: v[0] for k, v in parse_qs(parsed.query).items()},
                              headers=dict(self.headers), body=body)
            response = api.handle(request)
            payload = json.dumps(response.body).encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def log_message(self, fmt, *args):
            return

    return Handler


def serve(api: Api, host: str = "127.0.0.1", port: int = 8080) -> None:
    """`python3 -m tessera.api` starts this. Loopback only, no TLS, no CORS.

    That is deliberate: this is a development surface, and a development surface
    that silently listens on 0.0.0.0 is how a prototype ends up on the internet.
    A container overrides the host through TESSERA_HOST, and says so in the
    deployment files rather than by changing the default here.
    """
    from http.server import HTTPServer

    HTTPServer((host, port), handler_for(api)).serve_forever()


def demo_api(tenant_id: str = "018f0000-0000-7000-8000-000000000001",
             token: str = "demo-token") -> "Api":
    """A running API with sample data, for the container and for `python -m`.

    The token is printed by the entry point rather than baked into the image: a
    demo that ships with a known credential in it is a demo that ends up on the
    internet with a known credential in it.
    """
    import os
    import tempfile

    from .connectors import SimulatedConnector
    from .ledger import EventLog
    from .mesh import Mesh, Node
    from .projection import Projection

    path = os.path.join(tempfile.mkdtemp(prefix="tessera-demo-"), "ledger.jsonl")
    log = EventLog(path)
    mesh = Mesh(tenant_id, log)
    crm = SimulatedConnector("hubspot", "sales", page_size=10)
    support = SimulatedConnector("zendesk", "support", page_size=10)
    record = {
        "id": "018f0000-0000-7000-8000-00000000c001", "tenant_id": tenant_id,
        "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted", "lawful_basis": "consent", "purpose_id": "sales",
        "retention_policy_id": "rp-24m", "full_name": "Asha Rao",
        "email": "asha@example.com",
    }
    crm.seed("Contact", record)
    support.seed("Contact", dict(record, email="asha.rao@example.com"))
    mesh.register(Node("hubspot", crm, "sales", authority={"email": "authority"}, trust=0.8))
    mesh.register(Node("zendesk", support, "support", trust=0.6))
    mesh.sync("Contact")

    tokens = {
        token: Principal("demo", ("admin",), role="admin"),
    }
    return Api(tenant_id, tokens, log=log, mesh=mesh,
               projection=Projection(log, tenant_id).build())


def main() -> int:
    """`python3 -m tessera.api` - the container's entry point."""
    import os

    host = os.environ.get("TESSERA_HOST", "127.0.0.1")
    port = int(os.environ.get("TESSERA_PORT", "8080"))
    token = os.environ.get("TESSERA_TOKEN", "")
    api = demo_api(token=token or "demo-token")
    if not token:
        print("TESSERA_TOKEN is not set; serving with the demo token 'demo-token'")
        print("This is a development surface. Do not expose it.")
    print(f"listening on http://{host}:{port}")
    serve(api, host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
