# Audit method

**Status: Frozen**

## What was audited

`paste-1.md`, the 261-line build prompt titled "THE CRM FABRIC - Final Complete Build Prompt", as written. No
implementation existed, so the audit measured the specification, not a system.

## How

Four passes, in this order.

1. **Structural pass.** Every declared artefact was checked for a body. Layers, objects, deliverables, stages and
   inventions were counted and matched against their descriptions.
2. **Definition pass.** Every named score, threshold and guarantee was checked for a formula or an enforcement
   point. A term consumed more than once and defined zero times is a defect; a guarantee with no enforcement
   point is a defect.
3. **Contradiction pass.** Every pair of requirements that could not both hold was tested: write latency against
   per-write commits, profile contents against required features, autonomy tiers against review-queue routing,
   ICP against workforce value.
4. **External pass.** Statutory timing claims were checked against primary sources on 14 November 2026. Novelty
   claims were classified against named prior systems, not against intuition.

## What was checked against primary sources

| Claim | Source | Outcome |
|---|---|---|
| 72-hour breach intimation to the Data Protection Board | DPDP Rules 2025, rule 7(2), Gazette 13 Nov 2025 | Holds. The source document was right |
| 30-day DSAR clock | No statutory basis asserted | Does not hold. Parameterised per jurisdiction |
| AI Act transparency obligations | Consolidated AI Act, Article 113 as amended by the AI Omnibus | Enforceable from 2 Aug 2026 |
| AI Act Annex III high-risk obligations | Same, as amended | 2 Dec 2027. Annex I products 2 Aug 2028 |
| Consent architecture | DPDP Act 2023 s.6 and the Consent Manager regime | A single state field cannot carry purpose limitation |

## Severity definitions

| Severity | Meaning |
|---|---|
| Blocker | Construction cannot proceed correctly |
| Critical | A stated guarantee has no enforcement point |
| Major | The artefact is incomplete in a way a reviewer will find |
| Minor | Ambiguity that costs a decision, not a rewrite |

## What this audit does not do

It does not assess market size, competitive position or willingness to pay. It does not verify that the named
technologies can do what is claimed at the stated scale. It does not test code, because there is none.
