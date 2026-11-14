# 28 - Access control

**Status: Draft**

Deliverable 9, and the half of deliverable 18 that was blocked on it. Three layers, enforced at the read path in
one place, so every surface goes through the same gate.

| Layer | Question | Where |
|---|---|---|
| Object | May this role touch this object type at all? | `AccessPolicy.can_touch_object` |
| Field | May this role read this field, and edit it? | `can_read_field`, `can_edit_field` |
| Row | May this role see this record? | `can_read_row` |

The specification says "no client, API or MCP tool bypasses them". That is only true if the redaction happens in
one function every read path calls. If it happens in the handler, the next handler forgets.

## The one gate

Every read path calls `AccessPolicy`:

| Path | What it does |
|---|---|
| `GET /v1/objects/{object}` | filters rows, returns only visible ids |
| `GET /v1/objects/{object}/{id}` | redacts fields, or 404 if the row is invisible |
| `GET /v1/objects/{object}/export` | filters and redacts, because an export that forgets the policy is the classic leak |
| `GET .../history` | redacts the record inside each event payload |
| `GET .../as-of` | redacts the point-in-time record |
| `GET /v1/mesh/view/...` | drops denied fields and their conflicts |
| `POST .../fields/{field}` | refuses a field the role may not edit |
| MCP `get_record`, `get_unified_view`, ... | inherit, because they dispatch through the same handlers |

The history path is the one that gets missed. A ledger that stores full records will happily serve a denied field
back through an event payload, and the screen that hides the column is no protection at all.

## Roles

| Role | Objects | Reads | Edits | Rows |
|---|---|---|---|---|
| `admin` | all | all | all | all |
| `manager` | all | all | all | all |
| `rep` | contact, company, deal, activity, task, document | standard, sensitive | standard | owned |
| `support` | contact, company, ticket, activity, task, document | standard, sensitive | standard | owned |
| `auditor` | all | all | none | all |

Field classes: `billing` (deal and invoice amounts, currency, invoice number), `sensitive` (contact email, phone,
consent state, lawful basis), `standard` (everything else).

## Least privilege is the default

A principal with no declared role is an **auditor**: it may read every row and edit nothing.

A default of `admin` would be convenient and wrong, and the convenience is exactly how these layers rot. The
test asserts the default explicitly, because a security default that nobody tests is a security default that
gets changed by accident.

## Two rules that look like bugs and are not

**A rep reading a record it does not own gets 404, not 403.** A 403 confirms the record exists. For an
owner-scoped role the existence of somebody else's record is itself information.

**A denied field is dropped, not rejected.** A 403 on a field tells an unauthorised caller that the field exists
and holds something worth protecting. The response simply does not contain it.

## Ownership is a record-level field

`owner_seat_id` moved from `Contact` into the shared canonical envelope. Row-level access control needs it on
every object, and a rule that only works for contacts is not a rule. It is optional: a record with no owner is
invisible to an owner-scoped role, which is the safe direction.

## The criterion, tested six ways

Deliverable 9 says a denied field must be absent from the API, the export and the MCP output. Six tests, one per
surface:

| Surface | Test |
|---|---|
| API response | `test_denied_field_is_absent_from_the_api_response` |
| Export | `test_denied_field_is_absent_from_the_export` |
| MCP | `test_denied_field_is_absent_from_mcp_output` |
| History | `test_denied_field_is_absent_from_history` |
| Point in time | `test_denied_field_is_absent_from_as_of` |
| Unified view | `test_denied_field_is_absent_from_the_unified_view` |

Three surfaces would have satisfied the letter of the criterion. The other three are where the leak actually
happens.

## What is not here

- **No Postgres RLS.** The specification says row-level security is enforced by the database at query execution.
  Here it is enforced in Python, on every read path, which is the same guarantee for this implementation and a
  weaker one for a deployment that adds a second writer.
- **No per-tenant policy editing.** The policy is a Python object. A tenant cannot define its own roles yet.
- **No field-level encryption.** Denied fields are dropped from a response; they are not encrypted at rest,
  because there is no at-rest store.
- **No delegation or sharing.** A record is visible to its owner, its owner's managers, and nobody else. There is
  no "share with", and no team hierarchy.
- **No audit of denials.** A refusal is not written to the ledger. It probably should be, and it is not.

## Deliverables, updated

| Criterion | State |
|---|---|
| 9: OLS, FLS and RLS enforced at the read path | Met - in Python, not in Postgres |
| 9: denied field absent from API, export and MCP | Met - six tests, six surfaces |
| 9: DSAR lifecycle, retention engine, audit export | **Not met** |
| 18: every MCP tool passes the field and row access tests | **Met** - via the shared gate |
