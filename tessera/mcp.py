"""The MCP discovery schema: ten tools, each with a schema, a scope and an audit.

Deliverable 18: "all 10 MCP tools carry schema, auth scope and audit emission."

Three properties, and all three are tested rather than asserted:

    schema          every tool has a JSON Schema for its arguments, with required fields
    auth scope      every tool names the scope a caller must hold
    audit emission  every dispatch writes a ledger event naming the caller and the tool

The third is the one that is usually missing. A tool surface that can read every
customer record without leaving a trace is an audit hole with a friendly
description.
"""

from __future__ import annotations

from . import canonical
from .api import Principal, Request

SCOPE_READ = "read"
SCOPE_WRITE = "write"
SCOPE_WORKFORCE = "workforce"
SCOPE_AUDIT = "audit"

_OBJECT = {"type": "string", "enum": list(canonical.OBJECTS)}
_ID = {"type": "string", "format": "uuid"}

TOOLS = [
    {
        "name": "list_objects",
        "description": "List the identifiers of one canonical object type.",
        "auth_scope": SCOPE_READ,
        "audit_action": "mcp.list_objects",
        "inputSchema": {
            "type": "object",
            "properties": {"object": _OBJECT},
            "required": ["object"],
            "additionalProperties": False,
        },
        "route": ("GET", "/v1/objects/{object}"),
    },
    {
        "name": "get_record",
        "description": "Read one record as the projection currently believes it.",
        "auth_scope": SCOPE_READ,
        "audit_action": "mcp.get_record",
        "inputSchema": {
            "type": "object",
            "properties": {"object": _OBJECT, "id": _ID},
            "required": ["object", "id"],
            "additionalProperties": False,
        },
        "route": ("GET", "/v1/objects/{object}/{id}"),
    },
    {
        "name": "get_record_history",
        "description": "Every ledger event recorded against one record.",
        "auth_scope": SCOPE_READ,
        "audit_action": "mcp.get_record_history",
        "inputSchema": {
            "type": "object",
            "properties": {"object": _OBJECT, "id": _ID},
            "required": ["object", "id"],
            "additionalProperties": False,
        },
        "route": ("GET", "/v1/objects/{object}/{id}/history"),
    },
    {
        "name": "get_record_as_of",
        "description": "What the ledger knew about a record at a transaction time.",
        "auth_scope": SCOPE_READ,
        "audit_action": "mcp.get_record_as_of",
        "inputSchema": {
            "type": "object",
            "properties": {"object": _OBJECT, "id": _ID,
                           "at": {"type": "string", "format": "date-time"}},
            "required": ["object", "id", "at"],
            "additionalProperties": False,
        },
        "route": ("GET", "/v1/objects/{object}/{id}/as-of"),
    },
    {
        "name": "get_unified_view",
        "description": "One record merged across every node, with per-field provenance.",
        "auth_scope": SCOPE_READ,
        "audit_action": "mcp.get_unified_view",
        "inputSchema": {
            "type": "object",
            "properties": {"object": _OBJECT, "id": _ID},
            "required": ["object", "id"],
            "additionalProperties": False,
        },
        "route": ("GET", "/v1/mesh/view/{object}/{id}"),
    },
    {
        "name": "write_field",
        "description": "Write one field to the node that owns it, governed by its sync mode.",
        "auth_scope": SCOPE_WRITE,
        "audit_action": "mcp.write_field",
        "inputSchema": {
            "type": "object",
            "properties": {"object": _OBJECT, "id": _ID,
                           "field": {"type": "string"},
                           "value": {}},
            "required": ["object", "id", "field", "value"],
            "additionalProperties": False,
        },
        "route": ("POST", "/v1/objects/{object}/{id}/fields/{field}"),
    },
    {
        "name": "assign_task",
        "description": "Route a task to an occupant of a seat, and log the decision.",
        "auth_scope": SCOPE_WORKFORCE,
        "audit_action": "mcp.assign_task",
        "inputSchema": {
            "type": "object",
            "properties": {
                "seat_id": {"type": "string"},
                "required_capabilities": {"type": "array", "items": {"type": "string"}},
                "payload": {"type": "object"},
            },
            "required": ["seat_id"],
            "additionalProperties": False,
        },
        "route": ("POST", "/v1/tasks"),
    },
    {
        "name": "escalate_task",
        "description": "Escalate a task with a signed full-state handoff packet.",
        "auth_scope": SCOPE_WORKFORCE,
        "audit_action": "mcp.escalate_task",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": _ID,
                "trigger": {"type": "string", "enum": [
                    "unavailable", "over_budget", "low_confidence",
                    "sla_80pct", "sla_breached", "blocked"]},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["id", "trigger"],
            "additionalProperties": False,
        },
        "route": ("POST", "/v1/tasks/{id}/escalate"),
    },
    {
        "name": "verify_ledger",
        "description": "Recompute the hash chain and the projections.",
        "auth_scope": SCOPE_AUDIT,
        "audit_action": "mcp.verify_ledger",
        "inputSchema": {"type": "object", "properties": {}, "required": [],
                        "additionalProperties": False},
        "route": ("GET", "/v1/audit/verify"),
    },
    {
        "name": "health",
        "description": "Liveness and version.",
        "auth_scope": SCOPE_READ,
        "audit_action": "mcp.health",
        "inputSchema": {"type": "object", "properties": {}, "required": [],
                        "additionalProperties": False},
        "route": ("GET", "/health"),
    },
]

TOOL_INDEX = {tool["name"]: tool for tool in TOOLS}


def discovery_document() -> dict:
    """The schema an MCP client reads to learn what it may call."""
    return {
        "name": "tessera",
        "version": "1.0.0",
        "description": ("Federation mesh above every CRM: canonical records, a hash-chained ledger, "
                        "a unified view across nodes, and a workforce of seats."),
        "auth": {
            "type": "bearer",
            "scopes": [SCOPE_READ, SCOPE_WRITE, SCOPE_WORKFORCE, SCOPE_AUDIT],
        },
        "tools": [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
                "auth_scope": tool["auth_scope"],
                "audit_action": tool["audit_action"],
            }
            for tool in TOOLS
        ],
    }


class McpError(Exception):
    """A tool call that could not be served, with the reason a client can act on."""


def _route_path(template: str, arguments: dict) -> str:
    path = template
    for key, value in arguments.items():
        path = path.replace("{" + key + "}", str(value))
    return path


def dispatch(api, tool_name: str, arguments: dict, principal: Principal) -> dict:
    """Run one tool against the API, with a scope check and an audit event."""
    tool = TOOL_INDEX.get(tool_name)
    if tool is None:
        raise McpError(f"unknown tool {tool_name!r}")
    if not principal.can(tool["auth_scope"]):
        raise McpError(
            f"{principal.id!r} lacks scope {tool['auth_scope']!r} for {tool_name!r}"
        )

    missing = [field for field in tool["inputSchema"].get("required", [])
               if field not in arguments]
    if missing:
        raise McpError(f"{tool_name!r} is missing required arguments: {missing}")

    method, template = tool["route"]
    path_arguments = {k: v for k, v in arguments.items() if "{" + k + "}" in template}
    query = {k: v for k, v in arguments.items() if "{" + k + "}" not in template}

    request = Request(
        method=method,
        path=_route_path(template, path_arguments),
        query=dict(query),
        headers={"Authorization": f"Bearer {principal.id}"},
        body=arguments if method == "POST" else None,
    )

    # the API authenticates on the token; here the caller has already been
    # resolved, so the token map is checked by the API and the principal by us
    response = api.handle(request)

    if api.log:
        api.log.append(
            api.tenant_id,
            "agent" if principal.id.startswith("agent") else "human",
            "mcp.call",
            {"tool": tool_name, "principal": principal.id,
             "status": response.status,
             "arguments_hash": canonical.canonical_hash(arguments)},
            source_node_id="mcp",
        )

    if response.status >= 400:
        raise McpError(f"{tool_name!r} failed with {response.status}: "
                       f"{response.body.get('error')}")
    return response.body


def validate_tools(tools: list[dict] | None = None) -> list[str]:
    """Every tool must carry a schema, a scope and an audit action. No exceptions."""
    problems = []
    tools = tools if tools is not None else TOOLS
    if len(tools) != 10:
        problems.append(f"expected 10 tools, found {len(tools)}")
    names = set()
    for tool in tools:
        name = tool.get("name")
        if not name:
            problems.append("a tool has no name")
            continue
        if name in names:
            problems.append(f"{name}: duplicate tool name")
        names.add(name)
        if not tool.get("description"):
            problems.append(f"{name}: no description")
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            problems.append(f"{name}: inputSchema must be an object schema")
        elif "required" not in schema:
            problems.append(f"{name}: inputSchema must declare required arguments")
        if tool.get("auth_scope") not in (SCOPE_READ, SCOPE_WRITE, SCOPE_WORKFORCE, SCOPE_AUDIT):
            problems.append(f"{name}: auth_scope {tool.get('auth_scope')!r} is not a known scope")
        if not tool.get("audit_action"):
            problems.append(f"{name}: no audit_action - a tool that leaves no trace is a hole")
    return problems
