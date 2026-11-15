# Privacy

Version: 1.1
Effective: 15 November 2026
Owner: Dr Sohil Momin - sohilmomin2000@gmail.com
Changes: 1.1 — corrected. Version 1.0 said this repository "runs nowhere and makes no network request". That stopped
being true when `python3 -m tessera.api` and `python3 -m tessera.demo` landed, and a privacy document that describes a
repository which no longer exists is worse than none.

## What this repository is

TESSERA — a specification, a reference implementation, and a runnable API for a layer that federates CRM systems and
can act as the CRM itself.

## What it collects from you

**Nothing.** No analytics, no telemetry, no crash reporting, no tracking pixels, no email capture, no phone-home of
any kind. Nothing in this repository contacts the author.

## What the code does with data, when you run it

The reference implementation runs, and that changes the answer from "it collects nothing" to "it processes what you
give it, on your machine, and only where you point it":

| Component | Network behaviour |
|---|---|
| `python3 -m tessera.api` | Listens on `127.0.0.1`. Serves one tenant per process, or several through `TenantRouter` |
| `python3 -m tessera.demo` | Starts the API and serves a console directory on `127.0.0.1`. Prints a development token |
| The connectors | Make **no** network request unless you register one and point it at a live tenant. The shipped HubSpot, Salesforce and Zendesk connectors are exercised against recorded transports |
| The ledger | Writes to a file path you choose. In the demo, a temporary directory |

Personal data reaches this software only if you put it there. There is no hosted instance operated by the author.

## The product this specifies

The specification describes software that would process personal data on behalf of a business customer. If that
software is built, its privacy posture is a term of its own, and the commitments below are what the specification
requires of it:

- Personal data is processed only on a lawful basis recorded per record, against a stated purpose.
- Consent is notice plus purpose plus a recorded consent event, not a flag.
- A data subject request completes within a configured window, default 30 days, and produces a complete export.
- A personal data breach is intimated to the Data Protection Board and to each affected person without delay,
  with detailed information within 72 hours, per DPDP Rules 2025 rule 7.
- Retention is enforced by a policy engine with legal hold, not by memory.

Those are requirements in [docs/04-core.md](docs/04-core.md#compliance). They are not claims about anything that
exists.

## The 72-hour breach window — flagged, not asserted

Version 1.0 of this document cited "DPDP Rules 2025 rule 7" for breach intimation. That number has not been verified
against the notified text, and the second-hand reference used while drafting says rule 6. **Do not rely on either
until it is checked against the eGazette.** The obligation itself is section 8(6) of the Act: intimate the Board and
each affected Data Principal. The rule number is a detail a lawyer must confirm.

## Links that leave this repository

Documentation links to external sources for statutory references. Opening one takes you to that site under its
own privacy policy. This repository loads nothing from it.

## Changes

Every factual claim above is checkable against the code at the commit that carries this file: `grep -rn "fetch(\|urllib\|requests\." tessera/` lists every place the code can reach the network. If a future version adds a destination, this file changes in the same commit.

## What a lawyer must confirm

- The rule number and the exact window for breach intimation under the DPDP Rules, 2025.
- Whether shipping a runnable reference implementation changes the author's role under the Act, compared with
  shipping a specification alone.
- Whether the demo token printed to stdout constitutes a security disclosure obligation once the demo is run on a
  network the author does not control.

This document is a draft, not legal advice.

Contact: Dr Sohil Momin - sohilmomin2000@gmail.com
