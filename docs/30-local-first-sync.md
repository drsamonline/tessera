# 30 - Local-first sync

**Status: Draft**

Deliverable 4. One protocol, online or offline, and a convergence guarantee that is tested rather than asserted.

## The claim being tested

| Claim | Test |
|---|---|
| A client renders from its own store | `test_a_replica_renders_from_its_own_store` |
| A write made offline reconciles on reconnect with no lost update | `test_an_offline_write_reconciles_on_reconnect` |
| Concurrent mutations converge to one state | `test_a_thousand_mutations_converge` |
| Delivery order does not change the result | `test_delivery_order_does_not_change_the_result` |
| The same protocol serves both cases | `sync()` takes no mode argument |

## The protocol

```
sync(replica, server):
    ops  = replica.push()          # drain the outbox
    server.push(ops)               # accept, ignoring duplicates
    new, cursor = server.pull(replica.cursor)
    replica.pull(new)              # apply in whatever order they arrive
    replica.cursor = cursor
```

Three lines of state per client - an outbox, a cursor, and the store - and no branch for online versus offline.
A client that was disconnected for a second and a client that was disconnected for a week run the same code; the
outbox holds what it did and the cursor holds what it has seen.

## Why convergence is guaranteed and not likely

Field-level last-writer-wins over a Lamport counter, with the replica id as the tiebreak:

```
higher lamport wins
  equal lamport -> higher replica id wins
```

That is a **total order**, which is the whole argument. Any two operations on the same field are comparable, so
applying a set of operations in any order produces the same state. The test does it three ways - forward,
reversed, and shuffled - and asserts one fingerprint.

A thousand mutations across three replicas converge to one state. That number is in the test because the
specification's acceptance criterion says 1,000 and because a smaller number would not have caught an ordering
bug that only appears when a replica's counter and its id disagree about who wins.

## No lost update, stated precisely

Two replicas writing the same field produce one visible value and two logged operations:

```python
a.set(REF, "full_name", "From A")
b.set(REF, "full_name", "From B")
converge([a, b], server)
# both replicas: one value
# server.ops:    ["From A", "From B"]
```

The loser is **outranked, not deleted**. `test_the_losing_write_is_still_in_the_operation_log` asserts both
values survive in the log. The mesh's conflict resolver is where a human decides which one was right; the replica
state holds one value because an interface has to render something.

Two replicas writing *different* fields is not a conflict at all, and both survive. That is the case that
field-level LWW exists for: the naive record-level rule would have thrown one of them away.

## The ledger and the sync stream cannot disagree

Every accepted operation is written to the ledger as a `sync.op` event naming the replica that wrote it. So the
question "who changed this and from where" is answered by the same structure that answers "what did we know at
time T" - there is no second stream to reconcile.

## Deletion

A tombstone is a write to a reserved field, `__deleted__`, which means the merge rule needs no special case: a
tombstone with a higher Lamport outranks a field write with a lower one, and the field values stay underneath it.

**Resurrection is explicit.** `undelete()`, or a write to `__deleted__` with a higher Lamport. A plain field write
does not resurrect a deleted record, because an implicit resurrection would let a stale client bring back a record
somebody deliberately deleted - which is the failure a tombstone exists to prevent.

`sync.delete` reaches the ledger and the projection drops the record on rebuild, so deletion is not a replica-only
concept.

## What this is not

- **Not a CRDT.** No merge function, no counters that combine. Field-level LWW is simpler, converges, and loses
  information that a CRDT would keep. For a CRM field that is the right trade; for a collaborative text editor it
  would not be.
- **Not wall-clock ordering.** Lamport counters order causality. Two replicas that never met can produce the same
  counter value, and the replica-id tiebreak settles it deterministically rather than correctly.
- **Not a mesh.** `converge()` runs two rounds, which is enough for a hub. A peer-to-peer mesh needs more rounds
  and a gossip design, which is a network question rather than a protocol one.
- **No hard delete.** A tombstone hides a record and keeps its history, which is what an audit log requires and
  what a data subject request may not accept. R-07 in [29-compliance.md](29-compliance.md) is the same tension
  from the other side.
- **No encryption.** The transport is a Python function call. TLS, compression and batching belong to the
  transport, and there is no transport.
- **No browser client.** The replica is a Python object. OPFS SQLite and the SvelteKit client are specified and
  absent.

## Deliverable 4, updated

| Criterion | State |
|---|---|
| Client renders with the server stopped | Met - the replica state is local and complete |
| Offline write reconciles with no lost update | Met - the losing write is logged, not deleted |
| 1,000 concurrent mutations produce zero divergence | Met |
| One protocol serves online and offline | Met |
| A real client: OPFS SQLite, optimistic UI, browser | **Not met** |
| Deletion | Met - tombstone with explicit resurrection |
| Encrypted transport | **Not met** |
