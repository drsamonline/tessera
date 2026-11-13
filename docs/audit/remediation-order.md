# Remediation order

**Status: Frozen**

The defects are not independent. Five decisions unlock the rest, and making them in this order avoids rebuilding
artefacts twice.

| # | Action | Closes | Unblocks |
|---|---|---|---|
| 1 | Name one primary ICP; demote the other two to secondary and design constraint | F-01, F-02 | Every prioritisation decision |
| 2 | Rule on history authority: ledger authoritative, bi-temporal projected, git as checkpoints | C-02, C-03 | Relationship score, twin, disputes, audit |
| 3 | Publish the metric dictionary: weights, transforms, trust, relationship score, freshness | B-01 to B-04 | Router, conflicts, forecast |
| 4 | Reconcile deployment profiles and move the review queue to P1 | C-01, C-05, C-07 | P0 gate, Stage 3 scope |
| 5 | Attach acceptance criteria to all 22 deliverables | G-01 | Every acceptance report |
| 6 | Write the assumption register and permit recorded assumptions in place of questions | A-02 | All remaining gaps |
| 7 | Reclassify the 40 inventions and re-baseline the schedule | G-02, G-06 | Roadmap, diligence |
| 8 | Correct the compliance substrate to DPDP and classify AI actions at v1 | E-01 to E-04 | Enterprise sale |
| 9 | Write or strike Layers 3-5; write cross-cutting specs | A-01, A-05 | Document credibility |
| 10 | Prose pass: bound the absolutes, cut the triads | H-01 | Testability of everything above |

Steps 1 to 5 change the document's meaning and must precede any build. Steps 6 to 10 can run in parallel with
Stage 0.

## Where each fix landed

| Defect group | Fixed in |
|---|---|
| A-01, A-03, A-04, A-05, A-06 | [02-architecture.md](../02-architecture.md), [06-roadmap.md](../06-roadmap.md), [09-cross-cutting.md](../09-cross-cutting.md) |
| A-02 | [18-assumptions.md](../18-assumptions.md), [CONTRIBUTING.md](../../CONTRIBUTING.md) |
| B-01 to B-07 | [10-metrics.md](../10-metrics.md), [04-core.md](../04-core.md) |
| C-01 to C-07 | [11-history-authority.md](../11-history-authority.md), [13-deployment.md](../13-deployment.md) |
| D-01 to D-06 | [05-workforce.md](../05-workforce.md) |
| E-01 to E-05 | [04-core.md](../04-core.md), [research/compliance.md](../research/compliance.md) |
| F-01 to F-04 | [01-product.md](../01-product.md) |
| G-01 to G-06 | [15-build-sequence.md](../15-build-sequence.md), [16-acceptance-criteria.md](../16-acceptance-criteria.md), [14-invention-register.md](../14-invention-register.md) |
| H-01, H-02 | [17-constraints.md](../17-constraints.md), this repository's own structure |
