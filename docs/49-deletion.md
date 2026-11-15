# 49 — Deletion

**Status: Accepted, 15 November 2026**

## What a delete does

```
DELETE /v1/objects/{object}/{id}      body: {"reason": "..."}      scope: write
```

Three things happen, and one does not.

| Happens | Detail |
|---|---|
| An event is appended | `record.tombstoned`, carrying the reason, the principal, and `tombstone: true` |
| The projection forgets | The record leaves the list and a read returns `404` |
| The reason is kept | Forever, next to the tombstone |

| Does not happen | Why |
|---|---|
| The bytes are destroyed | See below. This is R-07, and it is still open |

## Why the reason is required

A deletion without a stated reason is indistinguishable from an accident six months later. The ledger is the thing
that survives, and "record 018f… was tombstoned" with no reason is an event nobody can act on. `reason_required` is a
`400`, not a warning.

## Why nothing is destroyed

An append-only hash chain cannot un-write a hash without breaking every hash after it. Destroying the bytes of a
record while keeping the chain intact is a cryptographic problem — crypto-shredding: encrypt each record with a
per-record key, and destroy the key. That is the correct answer and it needs a crypto dependency the engine does not
have, so R-07 stays open and documented rather than closed with a lie.

What the tombstone does buy is real: the record stops being served, the deletion is attributable, and the reason is on
the record. Under the DPDP Act that is the difference between "we deleted it" and "we can show when, why and on whose
instruction it was deleted".

## Idempotency

Deleting twice is `409 already_tombstoned`, not a second event. The tombstone index is rebuilt from the ledger on
first use, so it survives a restart — a tombstone outlives the process that wrote it.

## What the console does with it

The Delete action on a record asks for the reason before it will submit, and the toast says the record is tombstoned
rather than deleted. The word matters: one of those is true.
