# 11 - History and provenance authority

**Status: Frozen**

Three history mechanisms were specified in the source document and none was declared authoritative. This
document rules on it. *(Closes C-03.)*

## The ruling

| Mechanism | Role | Written by | Queryable as |
|---|---|---|---|
| UniversalEvent ledger | Authoritative record of every action | The ledger service only | The full history, always |
| Bi-temporal columns | Projection for point-in-time queries | A projection worker reading the ledger | A fast view of the same history |
| Git history | Checkpoint log over the ledger | A checkpoint worker, every 100 events or 30 s | A diffable, revertable timeline |

"What each system knew at time T" is answered by the ledger and by nothing else. The projections exist for speed
and must be rebuildable from the ledger. A projection that cannot be rebuilt is a defect.

## Why it matters more than it looks

This query is the product. It feeds the digital twin, the dispute trail, provenance and the audit chain. Three
mechanisms that can disagree means three possible answers, and a customer dispute will find the disagreement
before you do.

## Writes and commits

A write appends one ledger event and returns a local ack. A git checkpoint batches 100 events or 30 seconds.

This removes the contradiction between "every write is a commit" and a 50 ms write ack: the ledger is the
per-write record, git is the per-batch checkpoint, and both latencies are budgeted separately.
*(Closes C-02.)*

## Immutability and anchoring

Append-only Postgres is tamper-evident only against a party who does not control the database. The claim is made
true by external anchoring. *(Closes C-04.)*

- The chain head hash is published every 15 minutes to an external append-only log.
- A verification job recomputes the chain from genesis weekly and compares against the anchors.
- A fork or gap is a severity-1 incident with a published repair procedure: the affected range is quarantined,
  the anchor identifies the divergence point, and the range is replayed from the last good anchor.
- Customers receive a verification endpoint that proves their ledger range against the public anchors.

## What is not claimed

The ledger does not prove that an action was correct, lawful or wise. It proves that the action was recorded,
in an order, by an identified actor, and that the record has not changed since. Everything else is inference and
is labelled as such in the interface.
