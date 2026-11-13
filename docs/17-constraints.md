# 17 - Constraints

**Status: Frozen**

Unchanged from the source document, with the absolutes bounded so they can be tested. *(Closes H-01.)*

1. Do not design as a CRM first. The mesh is the product; the CRM core is one node.
2. Do not require migration to adopt. The mesh is additive.
3. Do not put AI in the critical path.
4. Do not label graph math, event sourcing, git operations or deterministic review queues as AI features.
5. Do not remove the relationship score, the forecast provenance ledger, branch what-if, the Markdown mirror or
   the review queue when AI is disabled.
6. Do not add AI-only fields or tables to the core schema.
7. Do not start AI containers by default in P0 or P1.
8. Do not assign tasks to users. Assign to seats; the router resolves occupants.
9. Do not allow an agent seat without `fallback_seat_id`.
10. Do not allow escalation without a HandoffPacket carrying full state.
11. Do not put an AI call inside the routing or workflow engine.
12. Do not silently overwrite a cross-CRM conflict.
13. Do not make any chain depend on a single node being online.
14. Do not allow a connector to skip the canonical schema.
15. Do not ship without backpressure and circuit breakers per node.
16. Do not ship without the boring features or the escape hatches.
17. Do not leak internal terms into the interface. Lint blocks release.
18. Do not ship a deliverable without its acceptance criterion.
19. Do not build anything that cannot run at P0 with zero AI containers.

## The boring features

Report builder (drag and drop, export), admin console (user management, audit viewer, restore), CSV import
wizard, point-in-time backup and restore, bulk operations with undo, list view customisation.

## The escape hatches

Raw SQL read-only, native schema export, direct API passthrough to any node, break-glass admin with audit.

These exist because a buyer who cannot leave will not arrive.
