"""Command line for the reference core.

    python3 -m tessera.cli demo [--keep]
    python3 -m tessera.cli mesh
    python3 -m tessera.cli timeline
    python3 -m tessera.cli workforce
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

from . import (canonical, checkpoint, conflict, conformance, ledger, metrics, mirror,
               projection, routing, workforce)
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


def cmd_timeline(args) -> int:
    """The ledger is the authority; everything else is rebuilt from it."""
    tmpdir = tempfile.mkdtemp(prefix="tessera-timeline-")
    log = ledger.EventLog(os.path.join(tmpdir, "ledger.jsonl"))
    ref = canonical.make_ref("Contact", CONTACT_ID)

    def record(**over):
        base = {
            "id": CONTACT_ID, "tenant_id": TENANT, "valid_from": "2026-11-01T09:00:00Z",
            "tx_time": "2026-11-01T09:00:01Z", "consent_state": "granted",
            "lawful_basis": "consent", "purpose_id": "sales-outreach",
            "retention_policy_id": "rp-24m", "full_name": "Asha Rao",
            "email": "asha@example.com",
        }
        base.update(over)
        return base

    _rule("1. Three writes, in the order the ledger saw them")
    log.append(TENANT, "system", "contact.sync",
               {"record": record(email="asha@example.com", valid_from="2026-11-01T09:00:00Z")},
               canonical_ref=ref, source_node_id="hubspot", timestamp="2026-11-01T09:00:00Z")
    log.append(TENANT, "system", "contact.sync",
               {"record": record(email="a.rao@example.com", valid_from="2026-11-03T09:00:00Z")},
               canonical_ref=ref, source_node_id="zendesk", timestamp="2026-11-03T09:00:00Z")
    # a correction that arrives late, and is true earlier than it was learned
    log.append(TENANT, "human", "contact.correct",
               {"record": record(email="asha.rao@example.com", valid_from="2026-11-02T09:00:00Z")},
               canonical_ref=ref, source_node_id="hubspot", timestamp="2026-11-10T09:00:00Z")
    for event in log.events(TENANT):
        print(f"  seq {event['sequence']}  {event['timestamp']}  {event['actor']:<6} "
              f"{event['action']:<16} {event['payload']['record']['email']}")

    _rule("2. What we knew, at a transaction time")
    proj = projection.Projection(log, TENANT).build()
    for at in ("2026-11-02T00:00:00Z", "2026-11-05T00:00:00Z", "2026-11-11T00:00:00Z"):
        print(f"  knew at {at}  {proj.as_of('Contact', CONTACT_ID, at).get('email')}")

    _rule("3. What was true, at a valid time")
    for at in ("2026-11-01T12:00:00Z", "2026-11-02T12:00:00Z", "2026-11-04T12:00:00Z"):
        print(f"  true at {at}  {proj.valid_at('Contact', CONTACT_ID, at).get('email')}")
    print()
    print("  the 10 November correction is true on 2 November but was not known until the 10th")
    print("  two questions, two answers, one ledger")

    _rule("4. The projection is rebuildable")
    result = proj.verify_rebuildable()
    print(f"  rebuildable  {result['rebuildable']}")
    print(f"  fingerprint  {result['live_fingerprint'][:16]}...")
    print(f"  events       {result['events_applied']} applied, {result['events_skipped']} skipped")

    _rule("5. Checkpoints: diff and revert without rewriting history")
    cp = checkpoint.Checkpointer(log, TENANT, os.path.join(tmpdir, "cp.jsonl"), every=1)
    cp.write()
    log.append(TENANT, "human", "contact.sync",
               {"record": record(email="wrong@example.com")},
               canonical_ref=ref, source_node_id="hubspot", timestamp="2026-11-12T09:00:00Z")
    cp.write()
    diff = cp.diff(0, 1)
    print(f"  diff 0->1    changed: {diff['changed']}")
    before = sum(1 for _ in log.events())
    cp.revert_to(0)
    after = sum(1 for _ in log.events())
    print(f"  revert       {before} events before, {after} after - it appends, it never deletes")
    print(f"  email now    {projection.Projection(log, TENANT).build().get('Contact', CONTACT_ID)['email']}")
    ok, problems = log.verify()
    print(f"  chain        {'OK' if ok else 'BROKEN'}")
    for problem in problems:
        print(f"  {problem}")

    _rule("6. The Markdown mirror, and how far behind it is")
    mirror_dir = os.path.join(tmpdir, "mirror")
    md = mirror.MarkdownMirror(log, TENANT, mirror_dir)
    written = md.mirror()
    print(f"  files        {written['files']} at sequence {written['sequence']}")
    print(f"  lag          {md.lag_events()} events")
    log.append(TENANT, "system", "contact.sync", {"record": record(email="later@example.com")},
               canonical_ref=ref, source_node_id="zendesk")
    print(f"  lag now      {md.lag_events()} events, visible rather than assumed")
    print(f"  verify       {md.verify()['ok']}")

    print()
    print(f"workspace {tmpdir}")
    return 0


def cmd_workforce(args) -> int:
    """Seats, not users. Four rules, each enforced."""
    tmpdir = tempfile.mkdtemp(prefix="tessera-wf-")
    log = ledger.EventLog(os.path.join(tmpdir, "ledger.jsonl"))
    wf = workforce.Workforce(TENANT, b"demo-key-not-a-secret", log=log)

    _rule("1. An agent seat cannot exist without a fallback seat")
    try:
        wf.register_seat(workforce.Seat(id="agent-responder", name="Responder", version=1,
                                        capability_manifest=["email"], occupant_type="agent"))
    except workforce.WorkforceError as exc:
        print(f"  refused: {exc}")

    wf.register_seat(workforce.Seat(id="triage", name="Triage", version=1,
                                    capability_manifest=["email", "triage"],
                                    sla_seconds=900, escalation_ladder=["specialist"]))
    wf.register_seat(workforce.Seat(id="specialist", name="Specialist", version=1,
                                    capability_manifest=["email", "refund"]))
    wf.register_seat(workforce.Seat(id="agent-responder", name="Responder", version=1,
                                    capability_manifest=["email"], occupant_type="agent",
                                    fallback_seat_id="specialist",
                                    escalation_ladder=["specialist"]))
    print("  triage, specialist and agent-responder registered")

    _rule("2. Occupants fill seats; humans and agents are interchangeable")
    wf.register_occupant(workforce.Occupant(id="priya", type="human", principal_id="p1",
                                            seat_id="triage", trust_score=0.9))
    wf.register_occupant(workforce.Occupant(id="sam", type="human", principal_id="p2",
                                            seat_id="specialist", trust_score=0.7))
    wf.register_occupant(workforce.Occupant(id="agent-1", type="agent", principal_id="p3",
                                            seat_id="agent-responder", trust_score=0.8,
                                            autonomy_tier="confirm_then_run"))
    for occ in wf.occupants.values():
        print(f"  {occ.id:<10} {occ.type:<6} seat {occ.seat_id:<16} trust {occ.trust_score}")

    _rule("3. A task routes to a seat, and the decision is logged")
    t = workforce.Task(id=canonical.uuid7(), seat_id="triage",
                       required_capabilities=["email"],
                       payload={"subject": "Where is my order?", "channel": "email"})
    decision = wf.assign(t)
    print(f"  occupant  {decision['id']}  score {decision['score']:.4f}  "
          f"({decision['weights_version']})")
    for name, part in decision["breakdown"].items():
        print(f"    {name:<20} {part['value']:.3f} x {part['weight']:.2f} "
              f"= {part['contribution']:+.4f}")

    _rule("4. Escalation carries a signed packet with full state")
    packet = wf.escalate(t.id, "low_confidence", evidence=["call-transcript-1"])
    print(f"  from      {packet.from_seat} -> {packet.to_seat}")
    print(f"  trigger   {packet.trigger}")
    print(f"  signature {packet.signature[:24]}...")
    print(f"  verifies  {packet.verify(wf.key)}")

    _rule("5. The receiver rebuilds the task from the packet alone")
    saved_seats, saved_tasks, saved_occ = wf.seats, wf.tasks, wf.occupants
    wf.seats, wf.tasks, wf.occupants = {}, {}, {}
    rebuilt = wf.receive(packet)
    wf.seats, wf.tasks, wf.occupants = saved_seats, saved_tasks, saved_occ
    print(f"  rebuilt   task {rebuilt.id[:8]}  seat {rebuilt.seat_id}")
    print(f"  payload   {rebuilt.payload['subject']}")
    print(f"  sla       {rebuilt.sla_deadline}")
    print("  nothing else was consulted")

    _rule("6. Revocation halts the agent, and fails closed")
    agent_task = workforce.Task(id=canonical.uuid7(), seat_id="agent-responder",
                                required_capabilities=["email"],
                                payload={"subject": "Refund request"})
    wf.assign(agent_task)
    print(f"  before    poll={wf.poll('agent-1')}  "
          f"act={'pending' if wf.act(agent_task.id, {'kind': 'send_email'})['pending'] else '?'}")
    wf.revoke("p3")
    print(f"  revoked   poll={wf.poll('agent-1')}")
    try:
        wf.act(agent_task.id, {"kind": "send_email"})
    except workforce.WorkforceError as exc:
        print(f"  refused   {exc}")
    print(f"  unknown   poll={wf.poll('nobody')} - an unknown occupant fails closed too")

    _rule("7. The ledger")
    ok, problems = log.verify()
    print(f"  events  {sum(1 for _ in log.events())}")
    print(f"  chain   {'OK' if ok else 'BROKEN'}")
    for problem in problems:
        print(f"  {problem}")

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

    p = sub.add_parser("workforce", help="seats, handoff, escalation, revocation")
    p.set_defaults(func=cmd_workforce)

    p = sub.add_parser("timeline", help="projection, point-in-time, checkpoints, mirror")
    p.set_defaults(func=cmd_timeline)

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
