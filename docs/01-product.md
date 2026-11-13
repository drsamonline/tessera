# 01 - Product definition

**Status: Frozen**

## What it is

TESSERA is a federation mesh that sits above existing business systems. A native CRM is one node in it, not
the product.

The mesh connects the systems a company already runs, presents one customer view, and records every action in
every connected system in a single hash-chained ledger. Adoption is additive: no migration is required to get
the first result, and the native core exists for accounts that want one system instead of five.

The product serves one founder and a 5,000-employee organisation on the same code paths. That is a constraint
on the architecture &mdash; tenant isolation, read models and pagination must not assume a size &mdash; not a
statement about who the first customer is.

## Customers

Three incompatible primary customers were named in the source document. One is primary, one secondary, and the
third is a design constraint. *(Closes defect F-01.)*

| Role | Segment | Why | What they buy |
|---|---|---|---|
| Primary | B2B agencies, 3-10 people, 3-5 disconnected SaaS tools | Enough people for seat-based routing to matter, small enough to adopt without procurement | One customer view across CRM, support and billing, plus one audit trail |
| Secondary | Solo founders | Fastest to activate, lowest support cost, but no workforce value | The unified view and the ledger; native core as their only CRM |
| Design constraint | 500-5,000 employee organisations | Not a v1 customer; their requirements bound the architecture | Federation across owned systems, residency, SSO, audit export |

The seat-based workforce layer is inert for a solo founder: one occupant fills every seat. The solo-founder path
is therefore the unified view plus ledger plus native core, and workforce value is sold to the primary segment.
*(Closes F-02.)*

## The activation event

"Aha moment at minute 4" is not measurable and cannot be an acceptance criterion. The activation event is:

> A tenant connects two nodes of different categories, and the first canonical Contact renders in the unified
> view with at least one linked Activity sourced from each node.

That event is the gate for onboarding (deliverable 19), for the bootcamp (deliverable 14) and for the beta
cohort definition. The 10-minute onboarding flow, the 4-minute target and the 30-minute switching-cost claim are
targets toward this event; the event itself is the test. *(Closes F-03, F-04.)*

## Category and distribution

Category name is used without variation: the mosaic layer above every CRM. Distribution is marketplace-led and
community-led: connectors and playbooks are the search surface, and published org designs are the sales motion.

## Non-goals

- Not a CRM to migrate onto. Migration is optional and always reversible.
- Not an AI product. AI is an optional occupant, disabled by default.
- Not a data warehouse. The mesh reads and writes systems of record; it does not become one by accident.
- Not a middleware platform for arbitrary integration. The connector contract is narrow on purpose.
