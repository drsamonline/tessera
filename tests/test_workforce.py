import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from tessera.ledger import EventLog
from tessera.workforce import (
    TERMINAL_HUMAN, TERMINAL_PARKED, HandoffPacket, Occupant, Seat, Task, Workforce,
    WorkforceError,
)

TENANT = "018f0000-0000-7000-8000-000000000001"
KEY = b"test-key-not-a-secret"
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def seat(seat_id="s1", **over):
    base = dict(id=seat_id, name=f"Seat {seat_id}", version=1,
                capability_manifest=["email", "triage"], sla_seconds=3600)
    base.update(over)
    return Seat(**base)


def occupant(occ_id="o1", seat_id="s1", **over):
    base = dict(id=occ_id, type="human", principal_id="p1", seat_id=seat_id)
    base.update(over)
    return Occupant(**base)


def task(task_id="t1", seat_id="s1", **over):
    base = dict(id=task_id, seat_id=seat_id, required_capabilities=["email"],
                payload={"subject": "Where is my order?", "channel": "email"})
    base.update(over)
    return Task(**base)


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-wf-")
        self.log = EventLog(os.path.join(self.dir, "ledger.jsonl"))
        self.wf = Workforce(TENANT, KEY, log=self.log)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def base_setup(self):
        self.wf.register_seat(seat("s1", escalation_ladder=["s2"]))
        self.wf.register_seat(seat("s2", capability_manifest=["email"],
                                   fallback_seat_id="s3"))
        self.wf.register_seat(seat("s3", capability_manifest=["email"]))
        self.wf.register_occupant(occupant("o1", "s1", trust_score=0.9))
        self.wf.register_occupant(occupant("o2", "s2", trust_score=0.4))


class TestSeatRules(Case):
    def test_agent_seat_without_fallback_is_rejected(self):
        with self.assertRaises(WorkforceError) as ctx:
            self.wf.register_seat(seat("agent", occupant_type="agent"))
        self.assertIn("fallback_seat_id", str(ctx.exception))

    def test_agent_seat_with_fallback_is_accepted(self):
        self.wf.register_seat(seat("human"))
        self.wf.register_seat(seat("agent", occupant_type="agent",
                                   fallback_seat_id="human"))
        self.assertIn("agent", self.wf.seats)

    def test_a_seat_cannot_be_its_own_fallback(self):
        with self.assertRaises(WorkforceError):
            self.wf.register_seat(seat("a", occupant_type="agent", fallback_seat_id="a"))

    def test_a_seat_cannot_escalate_to_itself(self):
        with self.assertRaises(WorkforceError):
            self.wf.register_seat(seat("a", escalation_ladder=["a"]))

    def test_version_must_start_at_one(self):
        with self.assertRaises(WorkforceError):
            self.wf.register_seat(seat("a", version=0))

    def test_unknown_occupant_type(self):
        with self.assertRaises(WorkforceError):
            self.wf.register_seat(seat("a", occupant_type="robot"))


class TestOccupants(Case):
    def test_occupant_needs_a_known_seat(self):
        with self.assertRaises(WorkforceError):
            self.wf.register_occupant(occupant("o1", "nope"))

    def test_unknown_status_rejected(self):
        with self.assertRaises(WorkforceError):
            self.wf.register_occupant(occupant(status="sleeping"))

    def test_unknown_tier_rejected(self):
        with self.assertRaises(WorkforceError):
            self.wf.register_occupant(occupant(type="agent", autonomy_tier="free_reign"))


class TestRouting(Case):
    def test_task_routes_to_the_best_occupant(self):
        self.base_setup()
        self.wf.register_occupant(occupant("o3", "s1", trust_score=0.3))
        decision = self.wf.assign(task(), now=NOW)
        self.assertEqual(decision["id"], "o1", "highest trust wins at equal capability")
        self.assertEqual(decision["weights_version"], "workforce-v1")

    def test_decision_is_logged_with_a_breakdown(self):
        self.base_setup()
        self.wf.assign(task(), now=NOW)
        events = [e for e in self.log.events(TENANT) if e["action"] == "task.assigned"]
        self.assertEqual(len(events), 1)
        payload = events[0]["payload"]
        self.assertEqual(payload["occupant"], "o1")
        self.assertIn("breakdown", payload)
        self.assertIn("capability_match", payload["breakdown"])
        self.assertIn("weights_version", payload)

    def test_inactive_occupants_are_skipped(self):
        self.base_setup()
        self.wf.register_occupant(occupant("o3", "s1", principal_id="p3", trust_score=0.5))
        self.wf.occupants["o1"].status = "paused"
        decision = self.wf.assign(task(), now=NOW)
        self.assertEqual(decision["id"], "o3")

    def test_revoked_occupants_are_skipped(self):
        self.base_setup()
        self.wf.register_occupant(occupant("o3", "s1", principal_id="p3", trust_score=0.5))
        self.wf.revoke("p1")
        decision = self.wf.assign(task(), now=NOW)
        self.assertEqual(decision["id"], "o3")

    def test_no_eligible_occupant_blocks_the_task(self):
        self.base_setup()
        self.wf.occupants["o1"].status = "off_shift"
        self.wf.occupants["o2"].status = "off_shift"
        with self.assertRaises(WorkforceError):
            self.wf.assign(task(), now=NOW)

    def test_seat_version_is_pinned_at_assignment(self):
        self.base_setup()
        t = task()
        self.wf.assign(t, now=NOW)
        self.assertEqual(t.seat_version, 1)
        self.wf.seats["s1"].version = 2
        self.assertEqual(t.seat_version, 1, "a later version does not change work in flight")

    def test_sla_deadline_is_set_from_the_seat(self):
        self.base_setup()
        t = task()
        self.wf.assign(t, now=NOW)
        self.assertEqual(t.sla_deadline, NOW + timedelta(seconds=3600))


class TestEscalation(Case):
    def setUp(self):
        super().setUp()
        self.base_setup()
        self.t = task()
        self.wf.assign(self.t, now=NOW)

    def test_escalation_builds_a_signed_packet(self):
        packet = self.wf.escalate("t1", "low_confidence", evidence=["call-1"], now=NOW)
        self.assertTrue(packet.verify(KEY))
        self.assertEqual(packet.from_seat, "s1")
        self.assertEqual(packet.to_seat, "s2")
        self.assertEqual(packet.evidence_refs, ["call-1"])

    def test_the_packet_carries_full_state(self):
        packet = self.wf.escalate("t1", "blocked", now=NOW)
        snapshot = packet.snapshot
        self.assertEqual(snapshot["payload"]["subject"], "Where is my order?")
        self.assertEqual(snapshot["required_capabilities"], ["email"])
        self.assertIn("sla_deadline", snapshot)
        self.assertIn("escalation_history", snapshot)

    def test_the_task_moves_to_the_next_seat(self):
        self.wf.escalate("t1", "unavailable", now=NOW)
        self.assertEqual(self.t.seat_id, "s2")
        self.assertIsNone(self.t.occupant_id, "the new seat must be routed again")
        self.assertEqual(len(self.t.handoff_chain), 1)

    def test_both_sla_clocks_are_recorded(self):
        self.wf.escalate("t1", "sla_80pct", now=NOW)
        row = self.t.escalation_history[-1]
        self.assertEqual(row["originating_sla_seconds"], 3600)
        self.assertEqual(row["receiving_sla_seconds"], 3600)

    def test_a_seat_without_a_ladder_cannot_escalate(self):
        self.wf.register_seat(seat("solo"))
        self.wf.register_occupant(occupant("o9", "solo"))
        self.wf.assign(task("t2", "solo"), now=NOW)
        with self.assertRaises(WorkforceError):
            self.wf.escalate("t2", "blocked")

    def test_unknown_trigger_is_rejected(self):
        with self.assertRaises(WorkforceError):
            self.wf.escalate("t1", "because")

    def test_the_escalation_is_logged(self):
        self.wf.escalate("t1", "over_budget", now=NOW)
        events = [e for e in self.log.events(TENANT) if e["action"] == "task.escalated"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["to"], "s2")

    def test_terminal_states(self):
        self.wf.terminate("t1", TERMINAL_PARKED)
        self.assertEqual(self.t.state, "parked")
        with self.assertRaises(WorkforceError):
            self.wf.terminate("t1", "abandoned")


class TestReceiveFromPacketAlone(Case):
    def test_the_receiver_needs_nothing_but_the_packet(self):
        self.base_setup()
        t = task()
        self.wf.assign(t, now=NOW)
        packet = self.wf.escalate("t1", "unavailable", now=NOW)

        # destroy everything the receiver might otherwise lean on
        self.wf.tasks.clear()
        self.wf.seats.clear()
        self.wf.occupants.clear()

        rebuilt = self.wf.receive(packet)
        self.assertEqual(rebuilt.id, "t1")
        self.assertEqual(rebuilt.payload["subject"], "Where is my order?")
        self.assertEqual(rebuilt.required_capabilities, ["email"])
        self.assertEqual(rebuilt.sla_deadline, NOW + timedelta(seconds=3600))
        # the packet describes the state at the moment of handoff, so it is not
        # yet in the chain it carries; the task gains it after the packet exists
        self.assertEqual(rebuilt.handoff_chain, [])

    def test_a_tampered_packet_fails_verification(self):
        self.base_setup()
        self.wf.assign(task(), now=NOW)
        packet = self.wf.escalate("t1", "unavailable", now=NOW)
        packet.snapshot["payload"]["subject"] = "Something else entirely"
        with self.assertRaises(WorkforceError):
            self.wf.receive(packet)

    def test_a_packet_signed_with_another_key_fails(self):
        self.base_setup()
        self.wf.assign(task(), now=NOW)
        packet = self.wf.escalate("t1", "unavailable", now=NOW)
        self.assertFalse(packet.verify(b"a-different-key"))


class TestRevocation(Case):
    def setUp(self):
        super().setUp()
        self.base_setup()
        self.wf.register_occupant(occupant("a1", "s1", type="agent", principal_id="p9",
                                           autonomy_tier="confirm_then_run"))
        self.wf.occupants["o1"].status = "paused"

    def test_an_agent_acts_before_revocation(self):
        self.wf.assign(task(), now=NOW)
        result = self.wf.act("t1", {"kind": "send_email"})
        self.assertTrue(result["pending"])

    def test_revocation_halts_the_agent(self):
        self.wf.assign(task(), now=NOW)
        self.wf.revoke("p9")
        self.assertTrue(self.wf.poll("a1"))
        with self.assertRaises(WorkforceError):
            self.wf.act("t1", {"kind": "send_email"})

    def test_revocation_is_logged(self):
        self.wf.revoke("p9")
        events = [e for e in self.log.events(TENANT) if e["action"] == "principal.revoked"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["principal_id"], "p9")

    def test_an_unknown_occupant_fails_closed(self):
        self.assertTrue(self.wf.poll("does-not-exist"))

    def test_revocation_does_not_touch_other_principals(self):
        self.wf.revoke("p9")
        self.assertFalse(self.wf.poll("o1"))


class TestAutonomy(Case):
    def setUp(self):
        super().setUp()
        self.base_setup()
        self.wf.register_occupant(occupant("shadow", "s1", type="agent", principal_id="p2",
                                           autonomy_tier="shadow_only", trust_score=0.95))
        self.wf.register_occupant(occupant("confirm", "s1", type="agent", principal_id="p3",
                                           autonomy_tier="confirm_then_run",
                                           trust_score=0.9))

    def test_shadow_only_discards(self):
        self.wf.assign(task(), now=NOW)
        self.assertEqual(self.wf.tasks["t1"].occupant_id, "shadow")
        result = self.wf.act("t1", {"kind": "send_email"})
        self.assertTrue(result["discarded"])
        self.assertFalse(result["applied"])

    def test_confirm_then_run_holds(self):
        self.wf.occupants["shadow"].status = "paused"
        self.wf.assign(task(), now=NOW)
        self.assertEqual(self.wf.tasks["t1"].occupant_id, "confirm")
        result = self.wf.act("t1", {"kind": "send_email"})
        self.assertTrue(result["pending"])
        self.assertFalse(result["discarded"])

    def test_the_two_tiers_are_observably_different(self):
        self.wf.assign(task("t1"), now=NOW)
        shadow = self.wf.act("t1", {"kind": "x"})
        self.wf.occupants["shadow"].status = "paused"
        self.wf.assign(task("t2"), now=NOW)
        confirm = self.wf.act("t2", {"kind": "x"})
        self.assertNotEqual(shadow["discarded"], confirm["discarded"])

    def test_an_agent_cannot_approve_its_own_proposal(self):
        self.wf.occupants["shadow"].status = "paused"
        self.wf.assign(task(), now=NOW)
        with self.assertRaises(WorkforceError):
            self.wf.approve("t1", {"action": {"kind": "x"}}, approver_id="confirm")

    def test_a_human_can_approve(self):
        self.wf.occupants["shadow"].status = "paused"
        self.wf.assign(task(), now=NOW)
        result = self.wf.approve("t1", {"action": {"kind": "x"}}, approver_id="o1")
        self.assertTrue(result["applied"])


if __name__ == "__main__":
    unittest.main()
