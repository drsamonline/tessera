# 29 - Compliance

**Status: Draft**

Reference: [04-core.md](04-core.md#compliance) and the statutory notes in
[research/compliance.md](research/compliance.md). Deliverable 9.

Four artefacts: consent, data subject requests, retention, and a signed audit export. One limitation, stated first
because it is the part a buyer will ask about.

## R-07: the ledger cannot honour an erasure request

The ledger is append-only and hash-chained. When a contact is erased, the event that recorded that contact still
holds that contact, and rewriting it breaks the chain the entire design rests on.

`erase()` therefore appends a tombstone. The projection drops the record, every read path stops serving it, and
the log records that the erasure happened and when. **The original payload remains in the log.**

This is a real defect in the design, not a documentation gap, and it is recorded as such:

| Option to close it | What it needs | Status |
|---|---|---|
| Crypto-shredding | Encrypt each subject's payload under a per-subject key; destroy the key on erasure. Old events become unreadable without touching the chain | Not implemented - needs a crypto dependency, and this repository has none |
| Segmented retention | Drop whole log segments past their window | Not implemented - needs a retention window shorter than the audit obligation, which for most tenants it is not |

Claiming erasure is implemented would be a lie, and the first data protection audit would find it in an afternoon.
The `erase()` result says `tombstoned, not destroyed` in its own return value so the caller cannot miss it.

## Consent is not a flag

```python
registry.grant("asha@example.com", "marketing", "notice-2026-01")
registry.is_permitted("asha@example.com", "support")     # False
```

A `consent_state` field cannot answer "may I use this for marketing" and "may I use this for support" differently.
That is the whole of purpose limitation, which is why the registry is keyed by purpose and why a grant requires
the notice version it was given under.

A lawful basis other than consent does not consult the registry, because a contract does not rest on consent.

## The DSAR clock is a configuration

Default 30 days, per-jurisdiction, and **not published as a statutory claim** until counsel confirms it. The
research note explains why: 30 days is a GDPR transplant, and DPDP does not set a deadline in that form.

The export is a complete bundle - every record the subject appears in, every consent record, every ledger event
that references them - with a `bundle_hash` over the whole thing. A partial export is worse than none, because it
looks like an answer.

`DsarService._current_state()` rebuilds the projection on every export rather than trusting the snapshot the
service was constructed with. A DSAR export that serves the state from before an erasure is worse than no export:
it is a confident, signed, wrong answer. The test that caught this is
`test_the_export_no_longer_contains_the_record`.

## Retention, and why legal hold wins

| Rule | Behaviour |
|---|---|
| `days` | A record past its window is due for expiry |
| `legal_hold=True` | The rule never fires, whatever the date. A hold outranks expiry, always |
| `sweep()` | Logs one `record.retention_expired` event per due record |

Expiry is a tombstone too, for the same reason erasure is: the log records that the record expired, and the
projection stops serving it on rebuild. `test_sweep_logs_and_the_projection_drops_the_record` asserts the record
is gone after a rebuild, not merely filtered in memory.

## The audit export is signed

```python
bundle = AuditExport(log, tenant, key).build("2026-11-01T00:00:00Z", "2026-11-30T00:00:00Z")
AuditExport(log, tenant, key).verify(bundle)     # True
```

The bundle carries the event hashes, the first and last hash of the range, and an HMAC over the whole body. Change
one number and verification fails. There is no default key.

An auditor can hold this file and verify it later without access to the database, which is the only version of an
audit export that is worth anything.

## What is not here

- **No real erasure.** See R-07.
- **No consent manager integration.** DPDP's Consent Manager regime is a registered intermediary; interoperability
  with one is not built.
- **No DSAR intake.** Requests are opened by an operator. There is no portal, no identity verification step, and
  no notification to the subject.
- **No record of processing.** The ROPA is a document the tenant writes, not something this code generates.
- **No cross-border transfer controls.** Residency is specified and absent.
- **No breach workflow.** The 72-hour clock is described in the specification and there is no code that runs it.

## Deliverable 9, updated

| Criterion | State |
|---|---|
| Object, field and row enforcement at the read path | Met - [28-access-control.md](28-access-control.md) |
| Denied field absent from API, export and MCP | Met - six tests, six surfaces |
| DSAR lifecycle with a tracked clock | Met - with a configurable, not statutory, clock |
| Complete DSAR export | Met - records, consent, events, hashed |
| Retention engine with legal hold | Met - expiry is a tombstone, not a deletion |
| Audit export | Met - signed, verifiable offline |
| Erasure that actually destroys the data | **Not met** - R-07 |
| Breach workflow, ROPA, residency | **Not met** |
