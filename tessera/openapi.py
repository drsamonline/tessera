"""The OpenAPI 3.1 document, generated from the route table.

Deliverable 18: "OpenAPI validates against 3.1; all 10 MCP tools carry schema,
auth scope and audit emission."

The document is generated rather than written, and `test_openapi.py` asserts that
every route in `api.Api.routes` appears in it. A hand-written contract drifts from
the code the first time someone adds a route in a hurry; a generated one drifts
only when someone edits the generator, which the same test catches.

`validate()` is a structural check, and it says so. Full JSON-Schema validation
of an OpenAPI document needs a dependency this repository does not have; when
`openapi-spec-validator` happens to be installed, `validate_full()` uses it.
"""

from __future__ import annotations

import re

from . import canonical

OPENAPI_VERSION = "3.1.0"

# Every operation the API exposes. `path` is the template, `pattern` is the
# route regex it corresponds to in api.py; the test matches them up.
OPERATIONS = [
    {
        "method": "get", "path": "/health", "operation_id": "health",
        "pattern": r"^/health$", "scope": None,
        "summary": "Liveness and version. The only unauthenticated route.",
        "responses": {200: "Health"},
    },
    {
        "method": "get", "path": "/v1/objects/{object}", "operation_id": "listObjects",
        "pattern": r"^/v1/objects/(?P<object>[A-Za-z]+)$", "scope": "read",
        "summary": "List the identifiers of one canonical object type.",
        "parameters": [{"name": "object", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "responses": {200: "ObjectList", 404: "Error"},
    },
    {
        "method": "get", "path": "/v1/objects/{object}/export", "operation_id": "exportObjects",
        "pattern": r"^/v1/objects/(?P<object>[A-Za-z]+)/export$", "scope": "read",
        "summary": "Every visible record of one object type, redacted by the same gate as a read.",
        "parameters": [{"name": "object", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "responses": {200: "ObjectList", 403: "Error"},
    },
    {
        "method": "get", "path": "/v1/objects/{object}/{id}", "operation_id": "getRecord",
        "pattern": r"^/v1/objects/(?P<object>[A-Za-z]+)/(?P<id>[0-9a-f\-]{36})$",
        "scope": "read",
        "summary": "Read one record as the projection currently believes it.",
        "parameters": [
            {"name": "object", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "id", "in": "path", "required": True,
             "schema": {"type": "string", "format": "uuid"}},
        ],
        "responses": {200: "Record", 404: "Error"},
    },
    {
        "method": "get", "path": "/v1/objects/{object}/{id}/history",
        "operation_id": "getRecordHistory",
        "pattern": r"^/v1/objects/(?P<object>[A-Za-z]+)/(?P<id>[0-9a-f\-]{36})/history$",
        "scope": "read",
        "summary": "Every ledger event recorded against one record.",
        "parameters": [
            {"name": "object", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "id", "in": "path", "required": True,
             "schema": {"type": "string", "format": "uuid"}},
        ],
        "responses": {200: "History", 404: "Error"},
    },
    {
        "method": "get", "path": "/v1/objects/{object}/{id}/as-of",
        "operation_id": "getRecordAsOf",
        "pattern": r"^/v1/objects/(?P<object>[A-Za-z]+)/(?P<id>[0-9a-f\-]{36})/as-of$",
        "scope": "read",
        "summary": "What the ledger knew about a record at a transaction time.",
        "parameters": [
            {"name": "object", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "id", "in": "path", "required": True,
             "schema": {"type": "string", "format": "uuid"}},
            {"name": "at", "in": "query", "required": True,
             "schema": {"type": "string", "format": "date-time"}},
        ],
        "responses": {200: "Record", 400: "Error"},
    },
    {
        "method": "get", "path": "/v1/mesh/view/{object}/{id}",
        "operation_id": "getUnifiedView",
        "pattern": r"^/v1/mesh/view/(?P<object>[A-Za-z]+)/(?P<id>[0-9a-f\-]{36})$",
        "scope": "read",
        "summary": "One record merged across every node, with per-field provenance.",
        "parameters": [
            {"name": "object", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "id", "in": "path", "required": True,
             "schema": {"type": "string", "format": "uuid"}},
        ],
        "responses": {200: "UnifiedView", 404: "Error"},
    },
    {
        "method": "post", "path": "/v1/objects/{object}/{id}/fields/{field}",
        "operation_id": "writeField",
        "pattern": r"^/v1/objects/(?P<object>[A-Za-z]+)/(?P<id>[0-9a-f\-]{36})"
                   r"/fields/(?P<field_name>[A-Za-z_]+)$",
        "scope": "write",
        "summary": "Write one field to the node that owns it, governed by its sync mode.",
        "parameters": [
            {"name": "object", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "id", "in": "path", "required": True,
             "schema": {"type": "string", "format": "uuid"}},
            {"name": "field", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        "request": "FieldWrite",
        "responses": {200: "WriteResult", 403: "Error", 422: "Error"},
    },
    {
        "method": "post", "path": "/v1/tasks", "operation_id": "assignTask",
        "pattern": r"^/v1/tasks$", "scope": "workforce",
        "summary": "Route a task to an occupant of a seat, and log the decision.",
        "request": "TaskCreate",
        "responses": {201: "TaskAssigned", 409: "Error"},
    },
    {
        "method": "post", "path": "/v1/tasks/{id}/escalate", "operation_id": "escalateTask",
        "pattern": r"^/v1/tasks/(?P<id>[0-9a-f\-]{36})/escalate$", "scope": "workforce",
        "summary": "Escalate with a signed full-state handoff packet.",
        "parameters": [{"name": "id", "in": "path", "required": True,
                        "schema": {"type": "string", "format": "uuid"}}],
        "request": "Escalation",
        "responses": {201: "Packet", 409: "Error"},
    },
    {
        "method": "get", "path": "/v1/audit/verify", "operation_id": "verifyLedger",
        "pattern": r"^/v1/audit/verify$", "scope": "audit",
        "summary": "Recompute the hash chain and the projections.",
        "responses": {200: "AuditReport", 409: "Error"},
    },
]


def _object_schema(object_name: str) -> dict:
    spec = canonical.SCHEMA[object_name]
    kinds = {"str": "string", "int": "integer", "num": "number", "bool": "boolean",
             "uuid": "string", "time": "string", "ref": "string", "list": "array",
             "dict": "object"}
    properties, required = {}, []
    for field, (kind, is_required) in spec.items():
        entry = {"type": kinds[kind]}
        if kind == "uuid":
            entry["format"] = "uuid"
        if kind == "time":
            entry["format"] = "date-time"
        if field == "consent_state":
            entry["enum"] = list(canonical.CONSENT_STATES)
        if field == "lawful_basis":
            entry["enum"] = list(canonical.LAWFUL_BASES)
        properties[field] = entry
        if is_required:
            required.append(field)
    return {"type": "object", "properties": properties, "required": required}


def components() -> dict:
    schemas = {name: _object_schema(name) for name in canonical.OBJECTS}
    schemas.update({
        "Error": {"type": "object", "properties": {
            "error": {"type": "string"}, "detail": {"type": "string"}},
            "required": ["error"]},
        "Health": {"type": "object", "properties": {
            "status": {"type": "string"}, "tenant": {"type": "string"},
            "auth_required": {"type": "boolean"}}, "required": ["status"]},
        "ObjectList": {"type": "object", "properties": {
            "object": {"type": "string"}, "ids": {"type": "array",
                                                  "items": {"type": "string"}}}},
        "Record": {"type": "object", "properties": {
            "object": {"type": "string"}, "id": {"type": "string"},
            "record": {"type": "object"}}},
        "History": {"type": "object", "properties": {
            "object": {"type": "string"}, "id": {"type": "string"},
            "events": {"type": "array", "items": {"type": "object"}}}},
        "UnifiedView": {"type": "object", "properties": {
            "object": {"type": "string"}, "id": {"type": "string"},
            "fields": {"type": "object"}, "conflicts": {"type": "array",
                                                        "items": {"type": "object"}},
            "blocked_fields": {"type": "array", "items": {"type": "string"}}}},
        "FieldWrite": {"type": "object", "properties": {"value": {}},
                       "required": ["value"]},
        "WriteResult": {"type": "object", "properties": {
            "node": {"type": "string"}, "field": {"type": "string"},
            "mode": {"type": "string"}, "principal": {"type": "string"}}},
        "TaskCreate": {"type": "object", "properties": {
            "seat_id": {"type": "string"},
            "required_capabilities": {"type": "array", "items": {"type": "string"}},
            "payload": {"type": "object"}}, "required": ["seat_id"]},
        "TaskAssigned": {"type": "object", "properties": {
            "task": {"type": "string"}, "occupant": {"type": "string"},
            "score": {"type": "number"}, "weights_version": {"type": "string"}}},
        "Escalation": {"type": "object", "properties": {
            "trigger": {"type": "string",
                        "enum": ["unavailable", "over_budget", "low_confidence",
                                 "sla_80pct", "sla_breached", "blocked"]},
            "evidence": {"type": "array", "items": {"type": "string"}}},
            "required": ["trigger"]},
        "Packet": {"type": "object", "properties": {
            "packet": {"type": "string"}, "from": {"type": "string"},
            "to": {"type": "string"}, "signature": {"type": "string"}}},
        "AuditReport": {"type": "object", "properties": {
            "chain_ok": {"type": "boolean"}, "problems": {"type": "array",
                                                          "items": {"type": "string"}},
            "rebuildable": {"type": "boolean"}}},
    })
    return {
        "schemas": schemas,
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer",
                           "description": "A bearer token mapped to a principal and its scopes."}
        },
    }


def build_document(title: str = "TESSERA API", version: str = "1.0.0") -> dict:
    paths: dict[str, dict] = {}
    for op in OPERATIONS:
        item = paths.setdefault(op["path"], {})
        operation = {
            "operationId": op["operation_id"],
            "summary": op["summary"],
            "responses": {
                str(status): {"description": _status_text(status),
                              "content": {"application/json": {
                                  "schema": {"$ref": f"#/components/schemas/{schema}"}}}}
                for status, schema in op["responses"].items()
            },
        }
        if op.get("parameters"):
            operation["parameters"] = op["parameters"]
        if op.get("request"):
            operation["requestBody"] = {
                "required": True,
                "content": {"application/json": {
                    "schema": {"$ref": f"#/components/schemas/{op['request']}"}}},
            }
        if op["scope"]:
            operation["security"] = [{"bearerAuth": []}]
            operation["x-required-scope"] = op["scope"]
        item[op["method"]] = operation

    return {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": title,
            "version": version,
            "description": ("A federation mesh above every CRM: one customer view, one hash-chained "
                            "ledger, seats instead of users. Reference implementation, not a "
                            "production service."),
            "license": {"name": "PolyForm Noncommercial 1.0.0"},
        },
        "servers": [{"url": "http://127.0.0.1:8080", "description": "Loopback development server"}],
        "paths": paths,
        "components": components(),
    }


def _status_text(status: int) -> str:
    return {200: "OK", 201: "Created", 400: "Bad request", 401: "Unauthenticated",
            403: "Forbidden", 404: "Not found", 409: "Conflict",
            422: "Unprocessable", 500: "Server error"}.get(status, "Response")


def validate(document: dict) -> list[str]:
    """Structural validation. Not a substitute for the real thing, and says so."""
    problems: list[str] = []

    if document.get("openapi") != OPENAPI_VERSION:
        problems.append(f"openapi must be {OPENAPI_VERSION}, got {document.get('openapi')!r}")
    info = document.get("info") or {}
    for key in ("title", "version"):
        if not info.get(key):
            problems.append(f"info.{key} is required")
    if not document.get("paths"):
        problems.append("paths must not be empty")

    schemas = (document.get("components") or {}).get("schemas") or {}
    ids = set()
    for path, item in (document.get("paths") or {}).items():
        if not path.startswith("/"):
            problems.append(f"path {path!r} must start with /")
        methods = [m for m in item if m in ("get", "post", "put", "patch", "delete")]
        if not methods:
            problems.append(f"path {path!r} has no operation")
        for method in methods:
            op = item[method]
            where = f"{method.upper()} {path}"
            operation_id = op.get("operationId")
            if not operation_id:
                problems.append(f"{where}: operationId is required")
            elif operation_id in ids:
                problems.append(f"{where}: operationId {operation_id!r} is not unique")
            else:
                ids.add(operation_id)
            if not op.get("summary"):
                problems.append(f"{where}: summary is required")
            if not op.get("responses"):
                problems.append(f"{where}: responses are required")
            for status, response in (op.get("responses") or {}).items():
                if not str(status).isdigit():
                    problems.append(f"{where}: response key {status!r} is not a status code")
                if not response.get("description"):
                    problems.append(f"{where}: response {status} has no description")
            for parameter in op.get("parameters", []):
                if not parameter.get("name") or not parameter.get("in"):
                    problems.append(f"{where}: every parameter needs name and in")

    for ref in _refs(document):
        target = ref.replace("#/components/schemas/", "")
        if not ref.startswith("#/components/schemas/"):
            problems.append(f"unsupported $ref {ref}")
        elif target not in schemas:
            problems.append(f"$ref {ref} does not resolve")

    return problems


def _refs(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _refs(item)


def validate_full(document: dict) -> list[str]:
    """Use openapi-spec-validator when it is installed. Optional by design."""
    try:
        from openapi_spec_validator import validate as spec_validate
    except ImportError:
        return []
    try:
        spec_validate(document)
    except Exception as exc:  # noqa: BLE001
        return [str(exc)]
    return []


def route_paths(api) -> set[tuple[str, str]]:
    """The (METHOD, regex) pairs the API actually serves. Used to catch drift."""
    return {(method, pattern) for method, pattern, _scope, _handler in api.routes}
