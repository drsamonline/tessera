# 54 - The landscape

**Status: Draft, 22 November 2026. Research, not advice.**

Five companies already sell what this project calls its category. This document names them, states what they do that
TESSERA does, and states what is left. It is written to be uncomfortable, because a positioning document that finds no
competitors has not looked.

## The five

| Company | What it sells | Overlap with TESSERA |
|---|---|---|
| **PipeMe** | Pipedrive, HubSpot, Salesforce and Dynamics connected in parallel, one view, one search, clean write-back. €19/seat/month annual, €29 monthly. 14-day trial, no card | **Direct.** Multi-CRM unified view, multi-tenant with row-level security, "for agencies and holdings" |
| **Racha** | HubSpot, Salesforce, Pipedrive, Zoho into one workspace; normalises owners, stages and amounts; one pipeline; leaderboards. $25/seat/month, three-seat minimum | **Direct.** Same pitch, same segment, already priced |
| **Syntaxia** | Schema mapping in place, entity resolution with confidence scores, **provenance per field**, schema drift detection, reversible merges | **Direct on the hardest part.** Provenance is TESSERA's central claim and Syntaxia ships it |
| **Stacksync** | Two-way sync with **per-field conflict policy**: last-write-wins, source-of-truth wins, longest-value, human-in-the-loop. Custom objects | **Direct on conflict resolution**, including the human-in-the-loop mode |
| **Knit / Unified.to** | A unified CRM API for developers: one schema, one auth, one pagination model across six CRMs | Adjacent. Infrastructure rather than a product |

## What this means, stated plainly

**"The mosaic layer above every CRM" is not an empty category.** It has at least three funded products, one of which
already prices at $25 per seat and one of which already ships per-field provenance. The pitch in this repository is not
novel, and a buyer who has looked will say so in the first meeting.

Three specific claims that must be retired or narrowed:

| Claim in this repository | Reality |
|---|---|
| "The mosaic layer above every CRM" as a category claim | PipeMe, Racha and Syntaxia all describe themselves this way |
| Per-field provenance as the differentiator | Syntaxia: *"Every record carries its complete provenance. Which source system contributed which fields"* |
| Human-in-the-loop conflict resolution | Stacksync ships it as a per-field policy option |

## What is actually left

Four things none of the five does. Each is a real difference and none of them is a category.

**1. A tamper-evident ledger.** None of the five mentions a hash chain, an append-only log, or verifiable history. They
record what the CRM says now. TESSERA can show that the record was not altered after the fact, and prove it with a
recomputed chain. This is the only claim in the repository that no competitor's marketing page touches.

**2. A workforce layer with seats, handoff packets and escalation.** None of the five has an idea of who is working a
record, what was handed over, or what happens when a person leaves. PipeMe and Racha sell to sales floors and stop at
leaderboards.

**3. Self-hosted and source-available.** All five are SaaS. A buyer who cannot send customer data to a vendor - a
hospital, a bank, a defence supplier, an Indian entity with a data-residency clause - has no option among them.

**4. A consent envelope on every record.** `consent_state`, `lawful_basis`, `purpose_id` and `retention_policy_id` are
required fields in the canonical schema. Under the DPDP Act that is the difference between a defensible record and an
indefensible one. None of the five exposes a lawful basis per record, and PipeMe's Enterprise tier sells "DPA and data
residency" as an add-on rather than a schema property.

## What that changes about the product

| Before | After |
|---|---|
| Sell to any team with two to four CRMs | Sell to teams that **cannot** use a SaaS unification layer, or that need provable history |
| Differentiate on the unified view | The unified view is table stakes. Differentiate on the ledger, the workforce layer and self-hosting |
| "Layer above every CRM" | "The CRM mesh you can host yourself, with a history you can prove" |

The second row is the one that costs something. The unified view, the conflict resolution and the provenance display are
the three things this project spent most of its effort on, and all three are now commodity features with published
price tags.

## What to do about it, in order

1. **Do not compete on the unified view.** It is built; it is not the pitch.
2. **Lead with the ledger.** It is the only claim here that is both true and unclaimed. The console already renders it,
   the chain verifies, and tampering is demonstrable in the browser.
3. **Price against self-hosting, not against seats.** A hospital cannot buy PipeMe at any price.
4. **Keep the CRM core.** A self-hosted mesh that is also the CRM when nothing else exists is a different product from a
   layer that needs four systems to be useful, and it is the version that sells to a customer with one spreadsheet.

## The honest caveat on this document

This is a week of desk research, not a market study. The five are the ones a search surfaced; there will be others,
including consultancies that do this as a project rather than a product. Pricing was read from public pages on 22
November 2026 and will move.

What it does establish is the thing that mattered: **the category is occupied, and the differentiators this project
assumed it had are not differentiators.**
