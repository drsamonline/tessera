# 19 - Open decisions

**Status: Draft**

Four items cannot be closed by assumption. They need a decision before Stage 1.

| # | Decision | Options | Consequence of deferring |
|---|---|---|---|
| 1 | Does the solo founder remain a supported segment at v1? | Keep as secondary, or drop to v2 | Onboarding, bootcamp and pricing all branch on this |
| 2 | Is the 44-sprint baseline accepted, or does v1 scope narrow? | Add people, cut deliverables, or accept a longer schedule | Stage 1 will silently absorb the gap |
| 3 | Which jurisdiction is the compliance default at launch? | India only, or India plus EU | DPIA scope, residency and DPA template all change |
| 4 | Does the review queue stay generic at P0, or does it become the proposal surface for every layer? | Generic queue, or per-layer queues | Affects the workforce layer's approval model |

## Decision 1 in detail

The primary segment is the 3-10 person agency. The solo founder is the fastest to activate and the least
profitable. Keeping both means two onboarding paths, two bootcamps and two value stories in the first release.
Dropping the solo founder simplifies v1 and loses the cheapest word-of-mouth channel.

## Decision 2 in detail

22 deliverables at a median of two sprints each is 44 sprints before parallelisation. The original plan said 30.
The gap is not a rounding error; it is a quarter. Accepting 44 is honest. Cutting to 30 means dropping three
deliverables, and the cheapest three to drop are the Academy (14, partly), the community platform (14) and the
mobile client (17).

## Decision 3 in detail

DPDP is the launch default because the customer base is Indian. Adding EU at launch doubles the DPIA scope and
requires an EU representative. Adding it at v1.1 is cheaper and defensible.

## Decision 4 in detail

A generic queue is one surface, one permission model and one audit trail. Per-layer queues are clearer to users
and triple the surface area. The workforce layer is the only one that needs approval semantics in v1.
