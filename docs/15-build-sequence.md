# 15 - Build sequence

**Status: Frozen**

Seven stages. 30 sprints at the original baseline, 44 at the stated capacity baseline.
*(Closes G-02, G-03, G-04.)*

| Stage | Sprints | Name | Deliverables | Exit criterion |
|---|---|---|---|---|
| 0 | 1-2 | Foundation | 1, 2, 18 | Repo, CI, design tokens v0, canonical schema v1 published and versioned, native core skeleton. Suite green at P0. |
| 1 | 3-8 | Mesh Core | 3 | Four connectors pass one conformance suite; ledger chain verifies; conflict resolution logged; unified view demonstrates the activation event. |
| 2 | 9-14 | Native Core | 4, 7, 8, 17 | Offline write reconciles with zero divergence; RVS reproducible to six decimals; git revert restores state; mobile outbox survives app kill. |
| 3 | 15-18 | Workforce | 5, 6 | Seat routing logged with breakdown; agent seat rejected without fallback; handoff reconstructs full state; AI playbook cannot execute unapproved. |
| 4 | 19-22 | Experience and Learning | 11, 12, 13, 14, 19 | Jargon lint fails the build on all 13 terms; activation event fires in scripted first run; migration rollback exact. |
| 5 | 23-26 | Security, Compliance, Boring | 9, 10, 15, 16 | FLS denial absent from API, export and MCP output; DSAR export complete; WCAG matrix attached; 5 locales render clean. |
| 6 | 27-30 | Beta and Launch | 20, 21, 22 | 10 ICP customers live; pre-audit hardening gate passed; external audit findings triaged with two remediation sprints reserved. |

## Capacity baseline

Six engineers, one designer, half an SRE. Estimate method: 22 deliverables at a median of two sprints
each gives 44 sprints before parallelisation. 30 is achievable only with more people or a narrower v1.
Replace the estimate with measured velocity after Stage 1. *(Assumption AS-18.)*

## Two ordering corrections

1. The canonical schema is versioned and conflict resolution lands before the second connector, so schema
   churn does not occur under a live integration.
2. A pre-audit hardening gate sits before Stage 6, with two sprints reserved for remediation findings.

## What each stage must prove

A stage is not complete when its code compiles. It is complete when the acceptance criteria for its
deliverables pass: [16-acceptance-criteria.md](16-acceptance-criteria.md).
