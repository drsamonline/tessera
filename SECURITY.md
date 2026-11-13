# Security Policy

> **Status:** Active (process statement only)
> **Last verified:** 2026-11-14

## Current security posture - read this first

**TESSERA has no implementation.** This repository contains a specification and three rendered documents. There
is no code to run, no service to attack and therefore **no security guarantee of any kind is claimed or
provided**.

The specification describes controls that *will* be built: three-layer access enforcement at query execution,
external anchoring of the audit chain, agent passports with 5-second revocation polling, and a fail-closed
default for any agent that cannot verify its principal. None of these are enforced today because none of them
exist.

## Reporting a vulnerability

When implementation code exists, report suspected vulnerabilities as follows:

1. Open a **private** security report via the repository's "Report a vulnerability" feature, if enabled;
   otherwise open a normal issue titled `security: <short summary>` without exploit details.
2. Include: affected commit, component, reproduction steps, and sanitized logs.
3. Never include customer data, credentials or anything you do not own.

A dedicated security contact address and a response-time commitment are **not published here because neither has
been confirmed by the project owner**. This section will be updated with real details when they exist, rather
than with a plausible-looking window.

## Design-level findings that are in scope now

The specification itself can have security defects. These are in scope:

- A control named in [docs/09-cross-cutting.md](docs/09-cross-cutting.md) with no enforcement point.
- A guarantee in [docs/12-ai-contract.md](docs/12-ai-contract.md) with no test.
- A conflict path that could silently overwrite data, contrary to
  [docs/03-mesh.md](docs/03-mesh.md#conflict-resolution).
- An audit-chain claim that does not survive the anchoring procedure in
  [docs/11-history-authority.md](docs/11-history-authority.md#immutability-and-anchoring).

Report those as ordinary documentation issues. They are the highest-value reports this repository can receive
right now.

## Supported versions

None released. Every artefact is pre-release and unsupported.
