# Compliance, checked 14 November 2026

**Status: Frozen**

Statutory timing claims in the specification, each with the source that settles it. Where the source does not
settle a question, the document says so rather than asserting an answer.

## India - DPDP Act 2023 and DPDP Rules 2025

The Rules were notified in the Gazette on 13 November 2025. Commencement is staged: rules 1, 2 and 17 to 21 on
publication; rule 4 (Consent Manager registration) one year later; rules 3, 5 to 16, 22 and 23 eighteen months
after publication.

| Question | Answer | Consequence for TESSERA |
|---|---|---|
| Is there a 72-hour breach clock? | Yes. Rule 7(2) requires detailed intimation to the Board within 72 hours of becoming aware, with immediate first intimation and notice to each affected Data Principal without delay | The source document's 72-hour workflow is correct and is retained |
| Is there a 30-day DSAR clock? | Not in the form the source document asserts. The Act sets rights; the clock is not a GDPR transplant | The DSAR clock becomes a per-jurisdiction configuration, default 30 days, unpublished until counsel confirms |
| Is consent a state field? | No. Consent must be free, specific, informed, unconditional and unambiguous, with a clear affirmative action, for a stated purpose | Consent is modelled as notice plus purpose plus record |
| What is a Consent Manager? | A registered intermediary acting for the Data Principal, India-incorporated, minimum net worth Rs. 2 crore, with its own obligations | Out of scope unless TESSERA registers as one. The consent model must remain interoperable |

Sources: DPDP Act 2023 (MeitY); DPDP Rules 2025, Gazette notification 13 November 2025; MeitY explanatory note to
the Rules.

## European Union - AI Act

The Act entered into force on 1 August 2024. The AI Omnibus, adopted 2026, reset the high-risk timeline.

| Obligation | Applies from | Consequence for TESSERA |
|---|---|---|
| Prohibited practices | 2 February 2025 | No prohibited practice is in scope |
| GPAI model obligations | 2 August 2025 | Relevant only to a provider of a general-purpose model, which TESSERA is not |
| Transparency obligations (Article 50) | 2 August 2026 | In force now. An agent that produces content or acts on records must disclose that it is an AI system |
| Annex III high-risk | 2 December 2027 | Includes employment and worker-management uses. The workforce layer must be classified before it is sold into the EU |
| Annex I embedded high-risk | 2 August 2028 | Out of scope |

Consequence: AI Act classification per AI action is a **v1 deliverable**. Deferring it entirely to v2 would leave
v1 agent occupants unclassified during a live transparency-obligation period. High-risk conformity work is
correctly deferred.

Sources: AI Act Service Desk consolidated text (Article 113, as amended); European Commission regulatory
framework page; Council of the EU timeline.

## What is not settled here

- Whether the workforce layer's seat routing falls inside Annex III worker-management scope. That is a legal
  question, not an engineering one.
- The exact DSAR response window that DPDP practice will settle on.
- Whether a tenant acting as a Data Fiduciary makes TESSERA a Data Processor in every configuration. It does in
  most, not all.

Each of these is recorded as an open item rather than answered by assumption.
