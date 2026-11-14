# 22 - Provider connectors

**Status: Draft**

HubSpot, Salesforce and Zendesk, written against their documented REST shapes, behind a transport seam so they
can be tested without a tenant, a token or a network.

## The honest caveat, first

**None of these three has been run against a live account.** Every test drives them through a recorded
transport that speaks the provider's documented shapes: the field names, the endpoint paths, the cursor format
and the wrapper objects come from public API documentation, not from a verified integration.

That is a real limitation and it is stated on every module, in the CHANGELOG and here. What it does mean: the
contract holds for a connector that speaks a foreign dialect, which is the thing a native connector could never
prove on its own.

## The seam

```python
from tessera.providers import HubSpotConnector
from tessera.transport import HttpTransport

node = HubSpotConnector("hubspot", HttpTransport(), tenant_id, token="...")
```

A connector never imports an HTTP library. It asks a `Transport` for a request and gets a `Response` or a
taxonomy error. Two transports ship:

| Transport | What it does |
|---|---|
| `HttpTransport` | Standard library `urllib`. Maps status codes onto the taxonomy: 401/403 `AuthError`, 429 `RateLimited` with `Retry-After`, 5xx `TransientError`, other 4xx `ContractError`, socket failure `TransientError` |
| `RecordedTransport` | Replays a handler and records every request, so a test can assert what was *sent*, not only what came back. It applies the same status classification, so a fixture returning 401 exercises the same path a live tenant would |

That last point matters: a test double that is more forgiving than production is a test double that hides the
bug.

## What each provider had to solve

| Provider | Endpoints | Cursor | Write response | The awkward part |
|---|---|---|---|---|
| HubSpot | `/crm/v3/objects/{contacts,companies,deals}` | `paging.next.after` | the object | a contact has `firstname` and `lastname`, never a name |
| Salesforce | `/services/data/v60.0/query`, `/sobjects/{Contact,Account,Opportunity}` | `nextRecordsUrl`, which replaces the request | `{id, success}` | every record carries an `attributes` block that is not data |
| Zendesk | `/api/v2/{users,tickets}` | `meta.after_cursor` with `page[after]` | `{user: {...}}` | the record is wrapped, and the name field is `name` |

Three providers, three cursor shapes, one contract. That is the argument for a conformance suite rather than a
reviewer.

## The envelope decision

A provider has never heard of `consent_state`, `lawful_basis`, `purpose_id` or `retention_policy_id`. A CRM does
not know your lawful basis. So the connector stamps them from its own configured policy, and the mesh records
that they were stamped rather than observed.

Identity works the same way, and it is the more interesting half:

- `id` is a UUIDv5 derived from the provider's identifier in a namespace scoped to the node, and is remembered
  in an identity map once the record has been written through the mesh.
- The external identifier never becomes the canonical identifier. A node can therefore be replaced without
  rewriting history, which is the whole reason the identity spine exists.
- The same external id in two nodes is two different records. The test asserts this, because it is the mistake
  a first implementation makes.

## Conformance

```
native:      16/16 checks passed
hubspot:     16/16 checks passed
salesforce:  16/16 checks passed
zendesk:     16/16 checks passed
```

Four connectors, one suite, run in the test file. A fifth connector is written the same way and must pass the
same sixteen checks before it ships.

```python
from tessera.conformance import assert_conforms
assert_conforms(HubSpotConnector("hubspot", HttpTransport(), tenant_id, token="..."))
```

## What is still not here

- **A live integration test.** No tenant, no token, no recorded real traffic. The next step is a single
  read-only sweep against a sandbox account, captured as a fixture, replacing the hand-built fakes.
- **Associations.** A HubSpot contact's company, a Salesforce contact's account, a Zendesk requester's
  organisation. The canonical schema has `company_ref` and the connectors do not populate it.
- **Webhooks.** `subscribe()` still raises for every provider.
- **Rate-limit accounting.** Each connector declares a rate limit; none enforces a token bucket.
- **Field-level sync modes.** The four modes exist as authority-map values; the connectors write everything the
  mesh tells them to write.

## Deliverable 3, updated

| Criterion | State |
|---|---|
| Canonical schema with 10 objects | Met |
| **Four connectors pass one shared conformance suite** | **Met** - native, HubSpot, Salesforce, Zendesk; the three providers against recorded transports, not live tenants |
| Ledger chain verifies | Met |
| A same-field conflict resolves deterministically and is logged | Met |
| Routing returns a term-by-term breakdown | Met |
| Write-back with sync modes | Partial - write-back to the declared owner works; the modes are modelled, not enforced per field |
| Backpressure per node | Not met - the circuit breaker exists, a token bucket does not |
