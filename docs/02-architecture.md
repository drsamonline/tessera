# 02 - Architecture

**Status: Frozen**

## The layer model

Eight layers were declared in the source document; five are specified in v1. The other three are roadmap with
entry criteria, not placeholders. *(Closes defect A-01.)*

| Layer | Name | v1 status | Specified in |
|---|---|---|---|
| 0 | Federation mesh | v1 | [03-mesh.md](03-mesh.md) |
| 1 | CRM core (optional native node) | v1 | [04-core.md](04-core.md) |
| 2 | Workforce | v1 subset | [05-workforce.md](05-workforce.md) |
| 3 | Intelligence | Roadmap, v2 | [06-roadmap.md](06-roadmap.md) |
| 4 | Protocol and settlement | Roadmap, v3 | [06-roadmap.md](06-roadmap.md) |
| 5 | Economic engine | Roadmap, v3 | [06-roadmap.md](06-roadmap.md) |
| 6 | Experience | v1 | [07-experience.md](07-experience.md) |
| 7 | Learning and enablement | v1 | [08-learning.md](08-learning.md) |
| &mdash; | Identity, observability, governance | v1 | [09-cross-cutting.md](09-cross-cutting.md) |

## Layer boundaries

Only one layer boundary had an interface contract in the source document. Every boundary now has one, and each
has an enforcement test. *(Closes A-04.)*

| Boundary | Contract | Enforcement test |
|---|---|---|
| Mesh to core | Canonical read/write API only. The core never reads a connector directly | Dependency test: no core module imports a connector module |
| Core to experience | Query and mutation API. No interface reads a table or an external node | Lint rule plus an API-surface test |
| Workforce to automation | `assign_to_seat` is the only entry point | The automation engine has no other workforce symbol in scope |
| Any layer to ledger | Append via the ledger API. No direct event-table writes | Schema test: no model writes the event table outside the ledger service |
| Any layer to AI | Proposal queue only. No synchronous AI call on a request path | Dependency test asserting no AI client is reachable from read, write, sync, auth, search, report or notification paths |

## Failure semantics

The connector interface had eight methods and no error model, so four connectors could not be built to one
contract. The error taxonomy is now part of the interface. *(Closes A-06.)*

| Error | Meaning | Handling |
|---|---|---|
| `TransientError` | Network or server fault | Retry with exponential backoff and jitter; counts toward the circuit breaker |
| `RateLimited` | The node is throttling | Carries `retry_after`; never counted as a node failure |
| `AuthError` | Credentials rejected | Halts the connector, raises an operator alert, never retried automatically |
| `SchemaDrift` | A field the canonical map expects is missing or retyped | Node enters degraded state; drift written to the ledger as an event |
| `PartialFailure` | A batch read returned some records | The connector must report the succeeded set explicitly |
| `ContractError` | The connector returned a shape the canonical schema forbids | Treated as a node defect, not a data defect |

Pagination is cursor-based and must terminate. A connector that cannot prove termination fails conformance.

## Isolation

Nothing in v1 may depend on a layer that is not in v1. The test is mechanical: no import from a v2 module in a
v1 code path.
