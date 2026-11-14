# 36 - Migration wizard

**Status: Draft**

Reference: [07-experience.md](07-experience.md#migration-as-experience). Deliverable 13.

A migration is three things the importer already knows how to do, in front of it, plus the two pieces that make
switching cost an hour rather than a day.

## The three steps

```
auto_map(headers, object)   guess the mapping from the source export's headers
transform(csv, mapping)     rewrite the file with canonical columns
dry_run / commit            hand it to the importer, which validates and logs
```

`transform` is where the awkward part lives: joining `First Name` and `Last Name` into `full_name`, and scaling a
deal amount from major to minor units. The importer stays simple because a migration is where source quirks belong,
not in the thing every import shares.

## Coverage, measured the honest way

The criterion is "maps at least 90% of fields automatically". The wizard reports two different numbers because they
answer two different questions:

- **Field coverage** - of the canonical fields a migration must fill, how many were mapped. This is the 90% number.
- **Unmapped columns** - source columns with no canonical home, listed rather than hidden.

| Source | Field coverage | Unmapped columns |
|---|---|---|
| HubSpot contact export | 100% | `Job Title`, `Company Name`, `Owner` |
| Salesforce contact export | 100% | `Website`, `Industry` |
| Zendesk user export | 100% | - |

A source column that carries a provider's own identifier is listed separately as a **source id**, because a
provider id is not a canonical uuid and pretending otherwise produces rows that fail validation.

## Two mappings the wizard refuses to guess

- **`owner_seat_id`.** A source system's owner is a name or a foreign identifier, not a canonical seat uuid.
  Auto-mapping it produced a column that failed validation on every row, which looks like a broken file rather
  than a mapping the wizard should not have guessed.
- **Amounts without a currency.** `Amount` maps to `amount_minor` and is scaled by 100; the currency column maps
  separately, and a row with an amount and no currency fails validation at the canonical layer rather than being
  assigned one.

## R-15, found by its own test

`Migration.commit()` cached the mapping from the first file it prepared. A second migration on the same object
silently reused the first file's headers, mapped nothing, and imported zero rows. The test that caught it commits
a Zendesk export and then a HubSpot one and asserts both land.

## Rollback restores the state exactly

`test_rollback_restores_the_prior_state_exactly` fingerprints the projection before a migration, runs it, rolls it
back, and asserts the fingerprint matches. A rollback that leaves the state merely *similar* is not a rollback.

## The two adoption pieces

**Keyboard translator.** `translate_shortcut("hubspot", "c")` returns `"n"`. An unknown shortcut is returned
unchanged rather than dropped: a translator that hides what it did not understand is a translator nobody trusts on
the second day.

**Template gallery.** Three installable objects - a pipeline with six stages, a support triage seat, and an org
design that wires two seats together. One click, one object graph, and the cheapest onboarding there is.

## Deliverable 13, updated

| Criterion | State |
|---|---|
| Dry run against HubSpot, Salesforce and Zendesk maps at least 90% of fields | Met - 100% field coverage on all three |
| Lists the remainder | Met - unmapped columns and source ids, separately |
| Rollback restores the pre-migration state exactly | Met - asserted by fingerprint |

## What is not here

- **No API-driven migration.** The wizard reads a CSV export. Pulling directly from a live tenant is the connector
  work in [22-providers.md](22-providers.md), and it is not wired to this.
- **No deduplication.** Importing the same contact twice creates two records; the deterministic dedup in
  [25-deterministic-features.md](25-deterministic-features.md) is not built.
- **No progress reporting.** A large file blocks.
- **No relationship migration.** Companies and their contacts arrive as separate files with no association.
- **No undo after a restart.** Batch ids live in memory.
