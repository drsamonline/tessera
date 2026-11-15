# 53 — Licensing

**Status: Accepted, 15 November 2026. A decision, not legal advice.**

## The decision

**Dual licensing.** PolyForm Noncommercial 1.0.0 for noncommercial use, a paid commercial licence for everything else.
[COMMERCIAL.md](../COMMERCIAL.md) is the offer; [LICENSE](../LICENSE) is unchanged apart from a header pointing at it.

## Why this structure works

PolyForm Noncommercial restricts **users**, not the licensor. That is the property that makes dual licensing possible
without touching the free grant: the copyright holder may offer the same code under different terms to different
people, and nothing already released becomes retroactively restricted.

A permissive licence (MIT, Apache) would have been simpler and would have let anyone — including a competitor with a
sales team — sell this without paying. On a product whose only moat is engineering, that is a donation with extra steps.

A fully proprietary licence was the other option and it is the wrong one here, for a reason specific to this project:

> The credibility of this repository rests on a reader being able to check the claims — 748 tests, a generated
> conformance report, a claim register with four rows marked *not verified*. A closed licence makes all of that
> unverifiable, and unverifiable evidence is marketing.

## What the free licence still permits

| Use | Permitted |
|---|---|
| Reading, running, testing, benchmarking | Yes |
| Personal projects, research, teaching | Yes |
| Evaluation inside a business, before purchase | Yes — this is the point |
| Modifying for any of the above | Yes |
| A revenue-generating deployment | **No. That needs a commercial licence** |

The boundary that matters and is narrower than it looks: **"we are only trialling it" stops being true the moment it
touches a paying customer's data.**

## What is deliberately not published

**No price list.** A published price is a commitment this project cannot keep before there is a customer, a support
model, or a deployment to price against. Terms are agreed per engagement.

**No support tier.** The licence grants rights, not hours.

## The trademark, which is a separate problem

"TESSERA" is a common English word and a mosaic term used by many products. The licence grants no trademark rights, and
this document does not claim any. Two consequences:

- A commercial customer should brand their deployment as their own.
- Registration, if wanted, is a question for an IP lawyer and probably a losing one for this word.

## What must be decided before the first invoice

| Question | Why it blocks |
|---|---|
| Is the buyer a company or a deployment? | Per-seat and per-tenant are different contracts |
| What happens when they stop paying? | The licence must say whether the deployed software keeps running |
| Who owns modifications? | The commercial licence should say, in one sentence |
| What is the support boundary? | A licence without a support definition invites an implied one |

## What a lawyer must confirm

- Enforceability of the dual structure in the intended jurisdiction.
- Whether the PolyForm noncommercial text covers the free tier as intended, particularly the internal-trial case.
- Whether the trademark position needs a disclaimer beyond the one in `COMMERCIAL.md`.
