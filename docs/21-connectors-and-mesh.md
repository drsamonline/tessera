# 21 - Connectors and the mesh

**Status: Draft**

The contract every connector implements, the suite that enforces it, and the smallest mesh that can
honestly be called one. Reference: [03-mesh.md](03-mesh.md).

## What is here

| Module | What it does |
|---|---|
| `tessera/connector.py` | The eight-method contract, the closed error taxonomy, the per-node circuit breaker, the retry wrapper |
| `tessera/connectors.py` | `NativeConnector`, `SimulatedConnector`, and `BrokenConnector` - the last one exists so the suite can be shown to reject |
| `tessera/conformance.py` | Sixteen checks, each independent and named, run against a live connector |
| `tessera/mesh.py` | Registration, sync, the unified view, conflict resolution wired to the ledger, write-back to the authority, and the activation event |

## The contract

```
capabilities() schema() read() write() subscribe() health() rateLimit() costEstimate()
```

Four of those eight are exercised by the suite. `subscribe()` is not implemented by any v1 connector and raises,
which is honest: a push subscription that silently does nothing is worse than an unimplemented one.

The error taxonomy is closed. A connector may raise `TransientError`, `RateLimited`, `AuthError`, `SchemaDrift`,
`PartialFailure` or `ContractError`, and nothing else. The suite checks this by reading an object the connector
does not carry and asserting the exception came from the taxonomy. A connector that raises `ValueError` fails
conformance, because a caller cannot apply a retry policy to an exception type it has never heard of.

| Error | Retried | Trips the breaker |
|---|---|---|
| `TransientError` | Yes, with exponential backoff | Yes |
| `RateLimited` | Yes, after `retry_after` | **No** - a throttled node is healthy and rude |
| `AuthError` | Never | Yes |
| `SchemaDrift` | Never | Yes |
| `PartialFailure` | Never | Yes |
| `ContractError` | Never | Yes |

## The conformance suite

Sixteen checks. The ones that matter:

- **`schema_maps_only_canonical_fields`** - a connector may not invent a field name. The canonical schema is the
  contract, and a mapping that points outside it is a mapping into a place the mesh cannot merge.
- **`read_pagination_terminates`** - walks cursors to the end with a hard cap of 100 pages. A connector that
  returns a cursor forever fails.
- **`write_is_idempotent`** - the same idempotency key twice must produce one record and one external id.
- **`write_rejects_invalid_payload`** - a payload missing a required field must be refused, and refused with a
  taxonomy error.
- **`round_trip`** - a written record must come back from a read. This is the check that catches a connector
  which accepts writes into a void.
- **`errors_are_from_the_taxonomy`** - see above.

```python
from tessera.conformance import assert_conforms
assert_conforms(MyConnector())      # raises with a named list if anything fails
```

### The suite is tested against a broken connector

`BrokenConnector` has nine modes, one per rule it can violate. The test file asserts that each mode fails the
check it is supposed to fail:

| Mode | Check that must catch it |
|---|---|
| `no_capabilities` | `capabilities_present` |
| `bad_schema` | `schema_maps_only_canonical_fields` |
| `bad_record` | `read_returns_valid_records` |
| `no_pagination` | `read_pagination_terminates` |
| `non_idempotent_write` | `write_is_idempotent` |
| `bad_health` | `health_is_valid` |
| `no_rate_limit` | `rate_limit_is_positive` |
| `negative_cost` | `cost_estimate_non_negative` |
| `wrong_error` | `errors_are_from_the_taxonomy` |

A conformance suite that only ever passes is a rubber stamp. This one is tested by what it rejects.

## The mesh

```python
mesh = Mesh(tenant_id, ledger)
mesh.register(Node("hubspot", connector, "sales", authority={"email": "authority"}, trust=0.8))
mesh.sync("Contact")
view = mesh.unified_view("Contact", contact_id)
mesh.activation()
```

`sync()` pulls every page from every node that carries the object, validates each record at the canonical
boundary, stores what passes and counts what does not. Every stored record writes one ledger event naming the
source node, so the ledger and the store cannot drift apart without the chain showing it.

`unified_view()` merges the candidates field by field:

| Situation | Rule recorded |
|---|---|
| One node carries the field | `single_source` |
| Every node reports the same value | `agreement` |
| A node declares `authority` for the field | `authority_map` |
| No owner, trust differs | `trust_score` |
| No owner, trust ties, valid times differ | `bi_temporal_recency` |
| Nothing separates them | `human_review` - the field blocks, the record does not |

`agreement` exists because two systems saying the same thing is not a conflict. Reporting it as one buries the
real disagreements in noise, and a conflict log nobody reads is the same as no conflict log.

`write_field()` refuses to guess. With no node declaring `authority` or `delegate` for a field, the write raises
`PermissionError`. A mesh that picks a winner for you is a mesh that corrupts one of your systems politely.

## The activation event, computed

[01-product.md](01-product.md) defines the event that has to be true on day one:

> A tenant connects two nodes of different categories, and the first canonical Contact renders in the unified
> view with at least one linked Activity sourced from each node.

`Mesh.activation()` returns whether that holds, with the evidence: the contact id, the categories, and which
nodes supplied activity. It is not a proxy metric and it is not a funnel step; it is the condition itself.

```bash
python3 -m tessera.cli mesh
```

Three nodes register, the suite runs against each, records sync, the unified view prints with provenance on
every field, the one real disagreement is shown with both values, the activation event is evaluated, a field is
written back to the node that owns it, and the chain verifies.

## What is still not here

- **Live provider integrations.** HubSpot, Salesforce and Zendesk connectors now exist and pass the same
  sixteen checks, but against recorded transports rather than live tenants:
  [22-providers.md](22-providers.md).
- **Push subscription.** `subscribe()` raises.
- **Backpressure and rate-limit accounting.** The breaker exists; a token bucket per node does not.
- **Conflict blocking in the interface.** A blocked field is reported by `unified_view()`; nothing renders it.
- **Postgres.** The store is a dictionary. Row-level security, bi-temporal columns and read replicas are
  specified and absent.

## Where this sits against the deliverables

Deliverable 3 is closer and still partial.

| Criterion | State |
|---|---|
| Canonical schema with 10 objects | Met |
| Four connectors pass one shared conformance suite | **Met** - native, HubSpot, Salesforce and Zendesk. The three providers are tested against recorded transports that speak their documented shapes, not against live tenants |
| Ledger chain verifies | Met |
| A same-field conflict resolves deterministically and is logged | Met |
| Routing returns a term-by-term breakdown | Met |
| Write-back with sync modes | Partial - write-back to the declared owner works, the four sync modes are modelled as authority modes and not enforced per field |
