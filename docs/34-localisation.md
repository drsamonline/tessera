# 34 - Localisation, currency and time

**Status: Draft**

Reference: [04-core.md](04-core.md#accessibility-globalisation-and-offline) and the jargon map in
[07-experience.md](07-experience.md). Deliverable 15.

## What is here

| Part | Where | What it does |
|---|---|---|
| Message catalogue | `locale.CATALOGUE` | 28 keys in 5 locales, with the jargon map as the interface vocabulary |
| Length budget | `locale.BUDGETS` | a declared character budget per key, checked across every locale |
| Formatter | `format_number`, `format_currency`, `format_date`, `format_time` | locale separators, minor units, per-user timezone |
| RTL mechanism | `direction`, `mirror` | a direction flag and a token mirror, tested against a pseudo-locale |
| Rate table | `RateTable` | historical conversion at the transaction date |

## The rendering claim is a proxy, and the doc says so

The specification asks that five locales **render without truncation on the twelve highest-traffic screens**. There
are no screens in this repository. What runs instead is `check_catalogue()`, which asserts three things a
translation actually breaks:

- every key exists in every locale
- no translation exceeds a declared character budget for its control
- no budget is declared for a key that does not exist

That catches a missing string and a string that outgrows its button. It does not catch a layout that was already
broken in English, and it cannot see a font fallback. Claiming it proves the rendering criterion would be
overclaiming.

RTL is the same shape: the mechanism exists and is tested against an `ar-x-mirror` pseudo-locale, and **no RTL
language ships in v1**. Shipping a half-translated one would be worse than shipping the mechanism.

## R-14, found by its own test

`mirror()` compared token names against lowercase literals, so `paddingLeft` and `paddingRight` both failed every
check and were copied through unchanged. An RTL layout that silently stayed LTR is exactly the failure the function
exists to prevent, and the test caught it on the first run.

## Currency is converted on the transaction date

```python
table.add("USD", "INR", 83.10, "2026-01-01")
table.add("USD", "INR", 84.25, "2026-06-01")
table.convert(100000, "USD", "INR", "2026-03-14")   # 8310000
table.convert(100000, "USD", "INR", "2026-07-01")   # 8425000
```

A rate is effective from its date until the next one for the same pair, and the boundary date is inclusive. A
conversion dated before the first rate **raises**: inventing a rate is how a finance report becomes fiction.

Amounts are stored in minor units and formatted for display. `test_currency_formatting_never_changes_the_value`
strips every non-digit from the formatted string and asserts the digits are unchanged across all five locales.

## Timezones

`format_date(moment, locale, tz)` converts before formatting. A deal that closes at 20:00 UTC is the 14th in UTC
and the 15th in Kolkata, and the test asserts both.

The offset table is a fixed lookup, not a tz database. That is enough to make the conversion real and the test
meaningful; a deployment needs `zoneinfo`, and the module says which it is.

## Deliverable 15, updated

| Criterion | State |
|---|---|
| Five locales | Met - 28 keys, 5 locales, complete and within budget |
| Renders without truncation on 12 screens | **Proxy only** - no screens exist; the budget check is what runs |
| RTL verified on 3 screens | **Mechanism only** - direction and mirror tested; no screens, no RTL locale shipped |
| Historical-rate conversion at the transaction date | Met |

## What is not here

- **No screens.** The whole rendering half of the criterion is untestable here.
- **No tz database.** A fixed offset table, stated as such.
- **No pluralisation or gender rules.** A message with a count needs a plural rule per language, and every key
  here is a label.
- **No translation workflow.** The catalogue is Python. A real product needs an external format and a review gate.
- **No number parsing.** Formatting is implemented; reading `1.234,56` back is not.
