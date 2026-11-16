# 48 — Standalone mode, and why the product is both things

**Status: Accepted, 14 November 2026**

## The decision

TESSERA is a federation layer **and** a CRM. It connects the systems a team already runs, and it is the system of
record when they run none.

This was a decision, not a drift. The console had grown contacts, companies, deals, notes, ownership and assignment —
a CRM's feature list, while the documents still described a layer above CRMs. Both halves are now stated.

## What standalone means, in full

| Question | Answer |
|---|---|
| Where does a record live with no CRM connected? | On the `native` node: an in-process store the mesh treats as one more node |
| Who is the system of record? | That node. `Mesh.primary_node` returns it, and a create writes there |
| Can it later federate? | Yes. Register a connector and the same record is a candidate like any other |
| Does it need Postgres? | No. The native node is in memory plus the ledger on disk |

## The compliance envelope is not defaulted

A record needs `consent_state`, `lawful_basis` and `purpose_id`. The mesh defaults none of them.

A record created with an invented lawful basis is a compliance claim nobody made, and under the DPDP Act that claim
has to be defensible. A caller that cannot state a lawful basis has not decided why it holds the data, and the
honest response is `422` rather than a plausible default.

`retention_policy_id` does default to `rp-default`, because a retention policy is a house rule rather than a
representation about a person.

## What changed in the API

```
POST /v1/objects/{object}   create a record on the primary node     scope: write
```

Three behaviours worth knowing:

- **One node, not four.** A create broadcast to every connected system produces four records with four ids, and
  reconciling them is the problem this layer exists to solve.
- **The projection is refreshed before the response.** A create that leaves the list empty is a create nobody
  believes, found by testing exactly that.
- **The event is `record.created`** in the ledger, with the principal in the payload. The ledger's actor vocabulary is
  `human`, `agent`, `system`; a principal id is none of those.

## What standalone still is not

- **No email, no calendar, no reporting, no mobile app.** It is a CRM for a team that needs a record of customers and
  a defensible history of changes, not a replacement for HubSpot's marketing surface.
- **No multi-tenancy in the store.** One tenant per process.
- **No backup beyond the ledger file.** The console has a workspace export; the engine has nothing equivalent yet.

## The honest comparison

A team choosing this over HubSpot is choosing a smaller product with an auditable history and no lock-in on where the
data lives. A team choosing it alongside HubSpot is choosing one screen over four. Both are the same code path, which
is the point.
