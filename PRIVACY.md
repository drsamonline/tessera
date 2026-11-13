# Privacy

Version: 1.0
Effective: 14 November 2026
Owner: Dr Sohil Momin - sohilmomin2000@gmail.com
Changes: Initial version.

## What this repository is

TESSERA - a specification for a federation layer that sits above existing business systems.

This repository is documentation. It runs nowhere, collects nothing and has no users.

## What it collects

**Nothing.** No analytics, no telemetry, no crash reporting, no tracking pixels, no email capture. There is no
code in this repository that makes a network request.

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

## Links that leave this repository

Documentation links to external sources for statutory references. Opening one takes you to that site under its
own privacy policy. This repository loads nothing from it.

## Changes

If a future version ever adds anything that carries your data, this file changes in the same commit.

Contact: Dr Sohil Momin - sohilmomin2000@gmail.com
