"""Command line for the reference core.

    python3 -m tessera.cli demo [--keep]
    python3 -m tessera.cli mesh
    python3 -m tessera.cli verify <ledger.jsonl>
    python3 -m tessera.cli anchor <ledger.jsonl> <anchor.jsonl>
    python3 -m tessera.cli history <ledger.jsonl> <tenant_id> <canonical_ref>

No dependencies. Nothing here reaches the network.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

from . import canonical, conflict, conformance, ledger, metrics, routing
from .connectors import NativeConnector, SimulatedConnector
from .mesh import Mesh, Node

TENANT = "018f0000-0000-7000-8000-000000000001"
HUBSPOT = "018f0000-0000-7000-8000-0000000000a1"
ZENDESK = "018f0000-0000-7000-8000-0000000000a2"
CONTACT_ID = "018f0000-0000-7000-8000-00000000c001"


def _rule(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def cmd_demo(args) -> int:
    tmpdir = tempfile.mkdtemp(prefix="tessera-")
    path = os.path.join(tmpdir, "ledger.jsonl")
    log = ledger.EventLog(path)

    ref = canonical.make_ref("Contact", CONTACT_ID)
    base = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)

    _rule("1. Two systems write the same contact")
    e1 = log.append(
        TENANT, "human", "contact.upsert",
        {"email": "asha@example.com", "full_name": "Asha Rao", "consent_state": "granted"},
        canonical_ref=ref, source_node_id=HUBSPOT,
        timestamp=base.isoformat().replace("+00:00", "Z"),
    )
    e2 = log.append(
        TENANT, "system", "contact.upsert",
        {"email": "asha.rao@example.com", "full_name": "Asha Rao", "consent_state": "granted"},
        canonical_ref=ref, source_node_id=ZENDESK,
        timestamp=(base + timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
    )
    print(f"  hubspot  seq {e1['sequence']}  {e1['payload']['email']}")
    print(f"  zendesk  seq {e2['sequence']}  {e2['payload']['email']}")

    _rule("2. What each system knew, at two different times")
    for hours, label in ((3, "12:00"), (9, "18:00")):
        at = (base + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
        known = log.knows_at(TENANT, ref, at)
        names = {"hubspot": HUBSPOT, "zendesk": ZENDESK}
        print(f"  at {label}")
        for node in (HUBSPOT, ZENDESK):
            for name, node_id in names.items():
                if node == node_id:
                    value = known.get(node_id, {}).get("email", "-  (had not written yet)")
                    print(f"    {name:<8} {value}")

    _rule("3. Conflict on the email field")
    result = conflict.resolve(
        "email",
        [
            conflict.Conflict(HUBSPOT, "asha@example.com", "2026-11-01T09:00:00Z", 0.72),
            conflict.Conflict(ZENDESK, "asha.rao@example.com", "2026-11-01T15:00:00Z", 0.72),
        ],
        authority_map={HUBSPOT: "authority", ZENDESK: "bidirectional"},
    )
    print(f"  rule    {result['rule']}")
    print(f"  winner  {result['winner']}")
    print(f"  value   {result['value']}")
    log.append(TENANT, "system", "conflict.resolved",
               conflict.to_event_payload(result), canonical_ref=ref,
               source_node_id=HUBSPOT)
    print("  logged  as one event, with both candidates and the rule")

    _rule("4. Routing: which node should take the write")
    ranked = routing.route([
        {"id": "hubspot", "estimated_cost": 1.0, "terms": {
            "capability_match": 1.0, "authority_match": 1.0, "sla_headroom": 0.8,
            "trust_score": 0.72, "utilization": 0.6, "cost_efficiency": 0.9,
            "data_freshness": 0.95, "cross_boundary_penalty": 0.0}},
        {"id": "zendesk", "estimated_cost": 2.0, "terms": {
            "capability_match": 0.5, "authority_match": 0.5, "sla_headroom": 0.9,
            "trust_score": 0.65, "utilization": 0.9, "cost_efficiency": 0.7,
            "data_freshness": 0.4, "cross_boundary_penalty": 0.0}},
    ])
    for row in ranked:
        print(f"  {row['rank']}. {row['id']:<9} {row['score']:.4f}")
    print()
    print(routing.explain(ranked[0]))

    _rule("5. Metrics")
    now = base + timedelta(days=30)
    obs = [{"at": now - timedelta(days=d), "success": d % 5 != 0, "escalated": False,
            "conflict": d % 7 == 0, "audit_complete": True} for d in range(40)]
    trust = metrics.trust_score(obs, now=now)
    print(f"  trust_score   {trust['score']:.4f}  (sample {trust['sample']}, "
          f"provisional {trust['provisional']})")
    thin = metrics.trust_score(obs[:5], now=now)
    print(f"  thin sample   {thin['score']:.4f}  (sample {thin['sample']}, "
          f"provisional {thin['provisional']})")

    interactions = [("meeting", now - timedelta(days=3)), ("email", now - timedelta(days=9)),
                    ("call", now - timedelta(days=20)), ("ticket", now - timedelta(days=40))]
    a = metrics.rvs(interactions, centrality=0.8, latency_asymmetry=0.4, now=now)
    b = metrics.rvs_alt(interactions, centrality=0.8, latency_asymmetry=0.4, now=now)
    print(f"  rvs           {a:.6f}  (second implementation {b:.6f}, "
          f"agree to 6dp: {abs(a - b) < 5e-7})")

    _rule("6. Verify the chain")
    ok, problems = log.verify()
    print(f"  events        {sum(1 for _ in log.events())}")
    print(f"  chain         {'OK' if ok else 'BROKEN'}")
    for p in problems:
        print(f"  {p}")
    anchor = log.anchor()
    print(f"  anchor head   {anchor['heads'][TENANT]['head'][:16]}...")

    _rule("7. Tamper with one byte, then verify again")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    lines[0] = lines[0].replace("Asha Rao", "Asha Roa")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    ok2, problems2 = ledger.EventLog(path).verify()
    print(f"  chain         {'OK' if ok2 else 'BROKEN'}")
    for p in problems2[:3]:
        print(f"  {p}")

    print()
    print(f"ledger written to {path}")
    if not args.keep:
        print("(kept for inspection; delete the directory when done)")
    return 0


def cmd_mesh(args) -> int:
    """Two nodes, one contact, one picture."""
    tmpdir = tempfile.mkdtemp(prefix="tessera-mesh-")
    log = ledger.EventLog(os.path.join(tmpdir, "ledger.jsonl"))
    mesh = Mesh(TENANT, log)

    crm = SimulatedConnector("hubspot", "sales", page_size=2)
    support = SimulatedConnector("zendesk", "support", page_size=2)
    native = NativeConnector(page_size=5)

    _rule("1. Three nodes register, each with an authority map")
    mesh.register(Node("hubspot", crm, "sales", authority={"email": "authority"}, trust=0.8))
    mesh.register(Node("zendesk", support, "support", trust=0.6))
    mesh.register(Node("native", native, "custom", trust=0.7))
    for node in mesh.nodes.values():
        print(f"  {node.id:<8} {node.category:<8} trust {node.trust}  "
              f"owns {list(node.authority) or 'nothing'}")

    _rule("2. Conformance: one suite, every connector")
    # Run against fresh instances: the suite writes test records, and seeding the
    # nodes that the demonstration then syncs would confuse the output.
    for fresh in (SimulatedConnector("hubspot", "sales"),
                  SimulatedConnector("zendesk", "support"),
                  NativeConnector()):
        print("  " + conformance.run_conformance(fresh).summary().replace("\n", "\n  "))

    _rule("3. Seed the systems and sync")
    ref = canonical.make_ref("Contact", CONTACT_ID)
    base = dict(
        id=CONTACT_ID, tenant_id=TENANT, valid_from="2026-11-01T09:00:00Z",
        tx_time="2026-11-01T09:00:01Z", consent_state="granted", lawful_basis="consent",
        purpose_id="sales-outreach", retention_policy_id="rp-24m", full_name="Asha Rao",
    )
    crm.seed("Contact", dict(base, email="asha@example.com"))
    support.seed("Contact", dict(base, email="asha.rao@example.com"))
    native.seed("Contact", dict(base, email="asha@example.com"))
    for i, (node_id, node, kind) in enumerate((("hubspot", crm, "email"),
                                               ("zendesk", support, "ticket")), start=1):
        node.seed("Activity", {
            "id": canonical.uuid7(ms=1_700_000_100_000 + i, rand=bytes([i] * 10)),
            "tenant_id": TENANT, "valid_from": "2026-11-01T10:00:00Z",
            "tx_time": "2026-11-01T10:00:01Z", "consent_state": "granted",
            "lawful_basis": "consent", "purpose_id": "sales-outreach",
            "retention_policy_id": "rp-24m", "kind": kind,
            "occurred_at": "2026-11-01T09:30:00Z", "subject_ref": ref,
            "body": f"logged by {node_id}",
        })
    print(f"  contacts  {mesh.sync('Contact')['stored']}")
    print(f"  activity  {mesh.sync('Activity')['stored']}")

    _rule("4. The unified view: one record, provenance on every field")
    view = mesh.unified_view("Contact", CONTACT_ID)
    print(f"  {'field':<22}{'value':<26}{'source':<14}rule")
    for name, cell in view["fields"].items():
        value = str(cell["value"])[:24]
        source = str(cell["source"])
        if source.count("+") >= 1:
            parts = source.split("+")
            source = f"{parts[0]}+{len(parts) - 1}"
        print(f"  {name:<22}{value:<26}{source:<14}{cell['rule']}")

    _rule("5. What actually disagreed")
    if view["conflicts"]:
        for c in view["conflicts"]:
            print(f"  {c['field']}: {c['rule']} -> {c['winner']}")
            for node_id, value in c["values"].items():
                print(f"    {node_id:<10} {value}")
    else:
        print("  nothing")
    print(f"  blocked fields: {view['blocked_fields'] or 'none'}")

    _rule("6. The activation event")
    activation = mesh.activation()
    print(f"  reached   {activation['reached']}")
    print(f"  contact   {activation.get('contact')}")
    print(f"  nodes     {activation.get('activity_sources')}")
    print(f"  evidence  {activation.get('evidence') or activation.get('reason')}")

    _rule("7. Write back, to the node that owns the field")
    result = mesh.write_field("Contact", CONTACT_ID, "email", "asha@rao.example.com")
    print(f"  wrote {result['field']}={result['value']} to {result['node']}")
    after = mesh.unified_view("Contact", CONTACT_ID)
    print(f"  unified view now: {after['fields']['email']['value']}")

    _rule("8. The ledger")
    ok, problems = log.verify()
    print(f"  events  {sum(1 for _ in log.events())}")
    print(f"  chain   {'OK' if ok else 'BROKEN'}")
    for problem in problems:
        print(f"  {problem}")
    print(f"  anchor  {log.anchor()['heads'][TENANT]['head'][:16]}...")

    print()
    print(f"workspace {tmpdir}")
    return 0


def cmd_verify(args) -> int:
    ok, problems = ledger.EventLog(args.path).verify()
    print("OK" if ok else "BROKEN")
    for p in problems:
        print(f"  {p}")
    return 0 if ok else 1


def cmd_anchor(args) -> int:
    record = ledger.EventLog(args.path).write_anchor(args.anchor_path)
    print(json.dumps(record, indent=2))
    return 0


def cmd_history(args) -> int:
    rows = ledger.EventLog(args.path).history(args.tenant, args.ref)
    if not rows:
        print("no events for that reference")
        return 1
    for row in rows:
        print(f"{row['sequence']:>4}  {row['timestamp']}  {row['actor']:<7} "
              f"{row['action']:<20} {row['hash'][:12]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tessera", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("demo", help="run the end-to-end demonstration")
    p.add_argument("--keep", action="store_true", help="keep the temporary ledger")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("mesh", help="run the federation demonstration")
    p.set_defaults(func=cmd_mesh)

    p = sub.add_parser("verify", help="verify a ledger's hash chain")
    p.add_argument("path")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("anchor", help="append the current chain heads to an anchor file")
    p.add_argument("path")
    p.add_argument("anchor_path")
    p.set_defaults(func=cmd_anchor)

    p = sub.add_parser("history", help="print the history of one canonical reference")
    p.add_argument("path")
    p.add_argument("tenant")
    p.add_argument("ref")
    p.set_defaults(func=cmd_history)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
