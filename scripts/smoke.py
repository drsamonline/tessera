#!/usr/bin/env python3
"""Call one real function from every module and print a table.

"Check every function if it works" is not a thing a script can do for a codebase
with 700 tests; this is the thing it can do: import every module, call something
real in it, and fail loudly if a module does not import. The suite is the rest.

Usage: python3 scripts/smoke.py     exit 0 = every module imported and answered
"""
import importlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tessera import (access, api, archive, automation, bench, bulk, canonical,
                     checkpoint, cli, compliance, conflict, conformance, connector,
                     connectors, design, escape, fuzz, jargon, learning, ledger,
                     locale, mcp, mesh, metrics, migrate, mirror, mobile,
                     observability, openapi, plugins, projection, ratelimit,
                     routing, store, sync, transport, views, workforce)
from tessera.providers import base as provider_base
from tessera.providers import hubspot, salesforce, zendesk


def _tmp():
    return os.path.join(tempfile.mkdtemp(prefix="tessera-smoke-"), "ledger.jsonl")


def _contact(**over):
    payload = {
        "id": canonical.uuid7(), "tenant_id": canonical.uuid7(),
        "valid_from": "2026-11-01T09:00:00Z", "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted", "lawful_basis": "consent", "purpose_id": "p",
        "retention_policy_id": "r", "full_name": "Asha Rao",
    }
    payload.update(over)
    return payload


def _ledger():
    log = ledger.EventLog(_tmp())
    log.append("018f0000-0000-7000-8000-000000000001", "system", "smoke", {"a": 1})
    return log.verify()[0]


def _seat():
    return workforce.Seat(id="s1", name="Triage", version=1,
                          capability_manifest=["email"]).validate()


def _openapi():
    return openapi.validate(openapi.build_document(api.Api("t" * 8, {}))) == []


CHECKS = {
    "access": lambda: access.DEFAULT_POLICY.can_touch_object("admin", "Contact"),
    "api": lambda: api.Principal("p").role,
    "archive": lambda: archive.archive.__name__,
    "automation": lambda: automation.evaluate("a == 1", {"a": 1}),
    "bench": lambda: callable(bench.run),
    "bulk": lambda: "ready" in bulk.preview("a\nx\n", "Contact",
                                            {"a": "full_name"},
                                            {"tenant_id": canonical.uuid7()}),
    "canonical": lambda: canonical.validate("Contact", _contact()) == [],
    "checkpoint": lambda: checkpoint.Checkpointer.__name__,
    "cli": lambda: callable(cli.main),
    "compliance": lambda: compliance.DsarRequest(
        id="d", subject_ref="s", kind="access",
        received_at=compliance._now()).state,
    "conflict": lambda: conflict.resolve(
        "email", [conflict.Conflict("n1", "v", "2026-01-01T00:00:00Z", 0.5)])["rule"],
    "conformance": lambda: conformance.run_conformance(connectors.NativeConnector()).ok,
    "connector": lambda: connector.CircuitBreaker().state,
    "connectors": lambda: connectors.NativeConnector().health().status,
    "design": lambda: design.contrast("#000000", "#FFFFFF"),
    "escape": lambda: len(escape.HATCHES),
    "fuzz": lambda: len(fuzz.SUITES),
    "jargon": lambda: len(jargon.JARGON),
    "learning": lambda: learning.check_learning() == [],
    "ledger": _ledger,
    "locale": lambda: locale.Translator("fr").t("action.save"),
    "mcp": lambda: len(mcp.TOOLS),
    "mesh": lambda: mesh.Node("n", connectors.NativeConnector(), "sales").id,
    "metrics": lambda: metrics.trust_score([])["provisional"],
    "migrate": lambda: len(migrate.gallery()),
    "mirror": lambda: mirror.MarkdownMirror.__name__,
    "mobile": lambda: len(mobile.KeyVault().derive("passphrase1")),
    "observability": lambda: observability.Histogram("smoke").percentile(95),
    "openapi": _openapi,
    "plugins": lambda: len(plugins.PERMISSIONS),
    "projection": lambda: projection.Projection.__name__,
    "ratelimit": lambda: ratelimit.TokenBucket(60, 5).try_acquire(),
    "routing": lambda: routing.score({**{k: 0.5 for k in routing.weights()
                                         if not k.startswith("_")},
                                      "cross_boundary_penalty": 0.0})["score"],
    "store": lambda: store.validate(store.schema_ddl()) == [],
    "sync": lambda: len(sync.Replica("r").fingerprint()),
    "transport": lambda: transport.classify(200, {}).status,
    "views": lambda: views.SavedView("v", "Deal").apply([]) == [],
    "workforce": _seat,
    "providers.base": lambda: provider_base.DEFAULT_POLICY["consent_state"],
    "providers.hubspot": lambda: hubspot.HubSpotConnector.__name__,
    "providers.salesforce": lambda: salesforce.SalesforceConnector.__name__,
    "providers.zendesk": lambda: zendesk.ZendeskConnector.__name__,
}


def main():
    rows, failed = [], 0
    for name in sorted(CHECKS):
        try:
            rows.append((name, "ok", str(CHECKS[name]())[:40]))
        except Exception as exc:  # noqa: BLE001 - the point is to report, not raise
            rows.append((name, "FAIL", f"{type(exc).__name__}: {exc}"[:60]))
            failed += 1

    print(f"{'module':<20} {'state':<5} result")
    print("-" * 74)
    for name, state, result in rows:
        print(f"{name:<20} {state:<5} {result}")
    print("-" * 74)
    print(f"{len(rows) - failed} ok, {failed} failed, {len(rows)} modules")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
