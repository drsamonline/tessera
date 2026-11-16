# 50 — Tenancy

**Status: Accepted, 15 November 2026**

## The shape

One process, several customers. `TenantRouter` picks the tenant from the bearer token and hands the request to that
tenant's own `Api`, which has its own `Mesh`, its own `EventLog` file and its own `Projection`.

```
token ──▶ TenantRouter ──▶ Api(tenant A) ──▶ Mesh ──▶ EventLog A
                      └──▶ Api(tenant B) ──▶ Mesh ──▶ EventLog B
```

## Why isolation by construction

The alternative is one mesh with a `tenant_id` column on every record and a `WHERE tenant_id = ?` on every read. That
design is one forgotten predicate away from a breach, and the predicate is forgotten in the one query nobody wrote a
test for.

Separate objects per tenant cannot leak through a missing filter, because there is no shared table to filter. It costs
memory proportional to tenants in a process, which is the right trade for a product with dozens of customers and the
wrong trade for one with millions, and this is the first.

## Two checks, two questions

| Where | Question |
|---|---|
| `TenantRouter` | **Which** tenant is this token for? Unknown token → `401`. |
| `Api` (per tenant) | **What** may this caller do? Scope and role. |

The router does not skip the tenant's own auth. A router that authenticated on behalf of everything below it would
mean the tenant's access policy was never applied on the routed path, the classic hole in a "we added a gateway"
change.

## What is proven

`tests/test_tenants.py`, eight tests:

- each token sees only its own records, and two tenants share no record id
- an unknown token is `401`; no token is `401`
- a create in one tenant does not appear in another
- one tenant cannot read another's record by id — `404`
- each tenant has its own ledger object
- `/health` names the tenants
- a token bound to a tenant with no runtime is `503 tenant_not_running`, not a `401` that sends someone to their token

## What is not done

- **No per-tenant quotas.** One tenant's sync loop can consume the process.
- **No per-tenant key management.** Encryption keys are not per tenant because there is no encryption yet.
- **No tenant provisioning API.** Tenants are built at start-up by a factory function.
- **No cross-tenant reporting.** Deliberate: an "admin across all tenants" token is the one that ends up in a support
  script.

## The demo

```bash
python3 -m tessera.demo --tenants 2 --standalone
```

prints one token per tenant and a link for the first. Each tenant has its own three seeded contacts, and creating a
record in one leaves the other untouched.
