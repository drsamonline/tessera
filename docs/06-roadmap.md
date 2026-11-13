# 06 - Roadmap layers (3, 4, 5)

**Status: Roadmap**

These three layers are deferred. They are written here so the deferral is a decision rather than an omission.
*(Closes A-01.)*

| Layer | Target | Entry criteria | Success criterion |
|---|---|---|---|
| 3 Intelligence | v2, months 16-24 | Graduated autonomy shipped; 90 days of outcome data per seat; review-queue approval rates stable | AI proposals accepted at a rate that beats the deterministic baseline on the same task set |
| 4 Protocol and settlement | v3, months 25-36 | Two tenants exchanging canonical objects under a signed contract; dispute trail exercised end to end | A third-party agent completes a transaction through the protocol with no bilateral integration |
| 5 Economic engine | v3, months 25-36 | Marketplace with provenance and revenue share live; metering accurate to the invoice | Revenue attributable to a published org design is measurable per publisher |

Nothing in v1 may depend on a layer that is not in v1. The test is mechanical: no import from a v2 module in a
v1 code path.

## Why these are deferred

Each of the three depends on data or counterparties that do not exist at launch. Intelligence needs outcome
history. Protocol needs a second tenant with a signed exchange agreement. The economic engine needs a
marketplace with live publishers. Building any of them early produces a demonstration, not a capability.

## What would move them earlier

A design partner who will sign an exchange agreement moves layer 4 forward by a year. Nothing else does.
