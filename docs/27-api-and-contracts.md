# 27 - The HTTP surface and the two contracts

**Status: Draft**

Deliverable 18: an OpenAPI document and an MCP discovery schema. Both are generated from one route table, so a
route cannot exist without appearing in the contract, and a test fails if they drift apart.

## Three properties, tested

| Property | Where | Test |
|---|---|---|
| Every request names a principal | `Api._authenticate` | `test_missing_token_is_401`, `test_wrong_scope_is_403` |
| Every mutation writes a ledger event naming the caller | `Api._audit` | `test_a_mutation_writes_an_audit_event_naming_the_caller` |
| Every tool call leaves a trace, including a failed one | `mcp.dispatch` | `test_every_dispatch_emits_an_audit_event` |

The third is the one usually missing from a tool surface. A tool that can read every customer record without
leaving a trace is an audit hole with a friendly description.

The audit event carries `arguments_hash`, not the arguments. A log that stores what was asked for is a second
copy of the data with weaker access control.

## The routes

| Method | Path | Scope |
|---|---|---|
| GET | `/health` | none - the only public route |
| GET | `/v1/objects/{object}` | read |
| GET | `/v1/objects/{object}/{id}` | read |
| GET | `/v1/objects/{object}/{id}/history` | read |
| GET | `/v1/objects/{object}/{id}/as-of?at=` | read |
| GET | `/v1/mesh/view/{object}/{id}` | read |
| GET | `/v1/objects/{object}/export` | read |
| POST | `/v1/objects/{object}/{id}/fields/{field}` | write |
| POST | `/v1/tasks` | workforce |
| POST | `/v1/tasks/{id}/escalate` | workforce |
| GET | `/v1/audit/verify` | audit |

Scopes are `read`, `write`, `workforce`, `audit`, and `admin` which covers all four.

## The OpenAPI document is generated, and checked twice

```
OpenAPI 3.1
  version    3.1.0
  paths      10
  operations 10
  schemas    23
  structural clean
  full spec  clean
```

Two checks, and the difference between them matters:

- **`validate()`** is a structural check written here: version, required info, one operation per path, unique
  operationIds, a response with a description for every status, resolvable `$ref`s, well-formed parameters. It
  runs everywhere, with no dependency.
- **`validate_full()`** uses `openapi-spec-validator` when it is installed, and skips visibly when it is not.
  A test that silently passes because its checker is absent is a test that reports good news it did not earn.

The 23 schemas are the 10 canonical objects generated from `canonical.SCHEMA`, plus the request and response
shapes. `test_required_fields_match_the_canonical_schema` asserts the generated `required` array equals the one
in the canonical schema, so the contract cannot drift from the validator.

## Ten tools, three properties each

| Tool | Scope | Audit action |
|---|---|---|
| `list_objects` | read | `mcp.list_objects` |
| `get_record` | read | `mcp.get_record` |
| `get_record_history` | read | `mcp.get_record_history` |
| `get_record_as_of` | read | `mcp.get_record_as_of` |
| `get_unified_view` | read | `mcp.get_unified_view` |
| `write_field` | write | `mcp.write_field` |
| `assign_task` | workforce | `mcp.assign_task` |
| `escalate_task` | workforce | `mcp.escalate_task` |
| `verify_ledger` | audit | `mcp.verify_ledger` |
| `health` | read | `mcp.health` |

`mcp.validate_tools()` returns a list of problems, and it is empty. A tool without a schema, a scope or an audit
action fails it, so the criterion is a test rather than a claim.

## Running it

```bash
python3 -m tessera.cli schema              # print and check both contracts
python3 -m tessera.cli schema --json mcp   # emit the discovery document
```

The server binds to loopback only:

```python
from tessera.api import Api, serve
serve(api)      # 127.0.0.1:8080, no TLS, no CORS
```

That is deliberate. A development surface that silently listens on `0.0.0.0` is how a prototype ends up on the
internet with a bearer token in a shell history.

## What this is not

- **Not a production gateway.** `http.server`, one thread, no TLS, no rate limiting, no request size cap, no
  CORS, no compression, no connection pooling.
- **No pagination.** A list route returns every identifier.
- **No idempotency keys on the HTTP surface.** The connectors have them; the API does not expose them.
- **No OpenAPI-driven routing.** The document is generated from the router, not the other way round. The drift
  test keeps them equal; it does not make the document authoritative.
- **No MCP transport.** The tools are defined and dispatchable in-process. There is no stdio or SSE server, so
  an MCP client cannot connect yet.

## Deliverable 18, updated

| Criterion | State |
|---|---|
| OpenAPI validates against 3.1 | Met - structurally always, fully when the validator is installed |
| All 10 MCP tools carry schema, auth scope and audit emission | Met |
| Every MCP tool passes the FLS and RLS tests from deliverable 9 | **Met** - the tools dispatch through the same gate as every other read path: [28-access-control.md](28-access-control.md) |
| An MCP server a client can connect to | **Not met** - in-process dispatch only |
