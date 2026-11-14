"""Reference benchmark.

    python3 -m tessera.bench            # measure, print, no verdict
    python3 -m tessera.bench --gate     # measure, print, exit 1 on a breach

What this is: a regression gate. The same shapes of work the product does, at a
size that finishes in seconds, so a change that makes the ledger three times
slower is caught before it ships.

What this is not: a load test. The targets in docs/04-core.md are stated for 1M
records per tenant, 200 concurrent users, 25 KB payloads and an 8 vCPU / 32 GB
host. None of those conditions hold here. Passing a target below does not
demonstrate load-model compliance, and this program never claims it does.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

from . import canonical, ledger, metrics, routing
from .connectors import SimulatedConnector
from .mesh import Mesh, Node
from .observability import REGISTRY, check_against_targets

TENANT = "018f0000-0000-7000-8000-000000000001"

# Regression thresholds at reference scale, in milliseconds. Not the load-model
# targets; a smaller number than docs/04 because the scale is a thousandth of it.
REGRESSION_TARGETS = {
    "ledger.append": {"p95": 5.0},
    "canonical.validate": {"p95": 1.0},
    "routing.score": {"p95": 1.0},
    "mesh.unified_view": {"p95": 20.0},
}


def _contact(i: int) -> dict:
    return {
        "id": canonical.uuid7(ms=1_700_000_000_000 + i, rand=bytes([i % 256] * 10)),
        "tenant_id": TENANT,
        "valid_from": "2026-11-01T09:00:00Z",
        "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted",
        "lawful_basis": "consent",
        "purpose_id": "sales-outreach",
        "retention_policy_id": "rp-24m",
        "full_name": f"Person {i}",
        "email": f"person{i}@example.com",
    }


def run(records: int = 2000) -> dict:
    REGISTRY.reset()
    tmpdir = tempfile.mkdtemp(prefix="tessera-bench-")
    path = os.path.join(tmpdir, "ledger.jsonl")
    log = ledger.EventLog(path)

    payloads = [_contact(i) for i in range(records)]

    for payload in payloads:
        with REGISTRY.timer("canonical.validate"):
            canonical.validate("Contact", payload)

    for payload in payloads:
        with REGISTRY.timer("ledger.append"):
            log.append(TENANT, "system", "contact.upsert",
                       {"email": payload["email"]},
                       canonical_ref=canonical.make_ref("Contact", payload["id"]),
                       source_node_id="bench")

    start = time.perf_counter()
    ok, problems = ledger.EventLog(path).verify()
    verify_ms = (time.perf_counter() - start) * 1000.0
    REGISTRY.observe("ledger.verify_whole_chain", verify_ms)

    terms = {"capability_match": 1.0, "authority_match": 1.0, "sla_headroom": 0.8,
             "trust_score": 0.7, "utilization": 0.6, "cost_efficiency": 0.9,
             "data_freshness": 0.9, "cross_boundary_penalty": 0.0}
    for _ in range(min(records, 5000)):
        with REGISTRY.timer("routing.score"):
            routing.score(terms)

    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    observations = [{"at": now, "success": True, "escalated": False,
                     "conflict": False, "audit_complete": True}] * 40
    for _ in range(min(records, 2000)):
        with REGISTRY.timer("metrics.trust_score"):
            metrics.trust_score(observations, now=now)

    # a mesh with two nodes and a slice of the same records
    mesh = Mesh(TENANT, None)
    crm = SimulatedConnector("hubspot", "sales", page_size=50)
    support = SimulatedConnector("zendesk", "support", page_size=50)
    mesh.register(Node("hubspot", crm, "sales", authority={"email": "authority"}, trust=0.8))
    mesh.register(Node("zendesk", support, "support", trust=0.6))
    slice_n = min(records, 500)
    for payload in payloads[:slice_n]:
        crm.seed("Contact", payload)
        support.seed("Contact", dict(payload, email="alt-" + payload["email"]))
    with REGISTRY.timer("mesh.sync"):
        mesh.sync("Contact")
    ids = mesh.record_ids("Contact")
    for record_id in ids[:slice_n]:
        with REGISTRY.timer("mesh.unified_view"):
            mesh.unified_view("Contact", record_id)

    return {
        "records": records,
        "verify_ok": ok,
        "verify_problems": problems[:3],
        "snapshot": REGISTRY.snapshot(),
    }


def _fmt(value: float) -> str:
    return f"{value:8.3f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tessera-bench", description=__doc__)
    parser.add_argument("--records", type=int, default=2000)
    parser.add_argument("--gate", action="store_true",
                        help="apply the regression thresholds and exit non-zero on a breach")
    args = parser.parse_args(argv)

    result = run(args.records)

    print()
    print("TESSERA reference benchmark")
    print(f"scale      {result['records']:,} records, one process, no network")
    print("note       this is NOT the load model in docs/04 (1M records, 200 users).")
    print("           it is a regression gate: same shapes, smaller size.")
    print()
    print(f"{'operation':<32}{'n':>8}{'p50':>9}{'p95':>9}{'p99':>9}{'max':>9}")
    print("-" * 76)
    for row in sorted(result["snapshot"], key=lambda r: -r["count"]):
        print(f"{row['name']:<32}{row['count']:>8}{_fmt(row['p50'])}"
              f"{_fmt(row['p95'])}{_fmt(row['p99'])}{_fmt(row['max'])}")
    print()
    print(f"chain verifies: {'yes' if result['verify_ok'] else 'NO'}")
    for problem in result["verify_problems"]:
        print(f"  {problem}")

    verdicts = check_against_targets(result["snapshot"], REGRESSION_TARGETS)
    print()
    print("regression thresholds (reference scale, not load-model targets)")
    for verdict in verdicts:
        mark = {"pass": "ok  ", "fail": "FAIL", "unmeasured": "?   "}[verdict["status"]]
        print(f"  {mark} {verdict['name']:<28} {verdict['detail']}")

    if not args.gate:
        return 0

    failed = [v for v in verdicts if v["status"] == "fail"]
    if failed or not result["verify_ok"]:
        print()
        print("GATE FAILED")
        return 1
    print()
    print("GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
