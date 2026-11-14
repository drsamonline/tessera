"""The workforce layer: seats, occupants, tasks, handoff, escalation, revocation.

Reference: docs/05-workforce.md.

The rule that makes this layer different from a ticketing system: **work is
assigned to a seat, never to a person**. A seat is a versioned, machine-readable
job description. A human or an agent occupies it. The router resolves which
occupant fills it, and the workflow layer never learns the answer.

Four guarantees, each enforced here rather than described:

    an agent seat cannot exist without a fallback seat
    an escalation cannot exist without a full-state handoff packet
    a packet is signed, and the receiver can rebuild the task from it alone
    revoking a principal halts its agents, and an agent that cannot verify its
        principal fails closed

The signature uses HMAC-SHA256 with a key the caller supplies. There is no
default key and no key in the source: a default key is not a signature, it is
decoration.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import canonical, routing

AUTONOMY_TIERS = ("shadow_only", "confirm_then_run")
OCCUPANT_TYPES = ("human", "agent", "hybrid")
STATUSES = ("active", "shadow", "paused", "off_shift")
TRIGGERS = ("unavailable", "over_budget", "low_confidence", "sla_80pct",
            "sla_breached", "blocked")

# The two terminal states an escalation ladder can end in. There is no third:
# a task that can neither be parked nor handed to a human is a task nobody has
# thought about.
TERMINAL_PARKED = "parked"
TERMINAL_HUMAN = "human_review_required"


class WorkforceError(Exception):
    """Raised when the workforce rules are violated."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------

@dataclass
class Seat:
    """A versioned, machine-readable job description."""
    id: str
    name: str
    version: int
    capability_manifest: list[str]
    permissions_scope: dict = field(default_factory=dict)
    sla_seconds: int = 3600
    cost_budget: float = 1.0
    fallback_seat_id: str | None = None
    escalation_ladder: list[str] = field(default_factory=list)
    occupant_type: str = "human"

    def validate(self) -> None:
        if self.occupant_type == "agent" and not self.fallback_seat_id:
            raise WorkforceError(
                f"seat {self.id!r} is an agent seat with no fallback_seat_id"
            )
        if self.occupant_type not in OCCUPANT_TYPES:
            raise WorkforceError(f"unknown occupant_type {self.occupant_type!r}")
        if self.version < 1:
            raise WorkforceError("a seat version starts at 1")
        if self.fallback_seat_id == self.id:
            raise WorkforceError(f"seat {self.id!r} cannot be its own fallback")
        if self.id in self.escalation_ladder:
            raise WorkforceError(f"seat {self.id!r} cannot escalate to itself")


@dataclass
class Occupant:
    id: str
    type: str
    principal_id: str
    seat_id: str
    status: str = "active"
    autonomy_tier: str = "confirm_then_run"
    trust_score: float = 0.5

    def validate(self) -> None:
        if self.type not in OCCUPANT_TYPES:
            raise WorkforceError(f"unknown occupant type {self.type!r}")
        if self.status not in STATUSES:
            raise WorkforceError(f"unknown status {self.status!r}")
        if self.type in ("agent", "hybrid") and self.autonomy_tier not in AUTONOMY_TIERS:
            raise WorkforceError(f"unknown autonomy tier {self.autonomy_tier!r}")


@dataclass
class Task:
    id: str
    seat_id: str
    required_capabilities: list[str]
    payload: dict
    state: str = "queued"
    sla_deadline: datetime | None = None
    assigned_at: datetime | None = None
    seat_version: int = 1
    occupant_id: str | None = None
    handoff_chain: list[str] = field(default_factory=list)
    escalation_history: list[dict] = field(default_factory=list)
    outcome: str | None = None

    def snapshot(self) -> dict:
        """Full state, for the packet. Not a summary: a summary loses the thing
        the receiver needs."""
        return {
            "id": self.id,
            "seat_id": self.seat_id,
            "seat_version": self.seat_version,
            "required_capabilities": list(self.required_capabilities),
            "payload": dict(self.payload),
            "state": self.state,
            "sla_deadline": _iso(self.sla_deadline) if self.sla_deadline else None,
            "assigned_at": _iso(self.assigned_at) if self.assigned_at else None,
            "occupant_id": self.occupant_id,
            "handoff_chain": list(self.handoff_chain),
            "escalation_history": [dict(row) for row in self.escalation_history],
            "outcome": self.outcome,
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "Task":
        def parse(value):
            return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

        return cls(
            id=snapshot["id"],
            seat_id=snapshot["seat_id"],
            required_capabilities=list(snapshot["required_capabilities"]),
            payload=dict(snapshot["payload"]),
            state=snapshot["state"],
            sla_deadline=parse(snapshot.get("sla_deadline")),
            assigned_at=parse(snapshot.get("assigned_at")),
            seat_version=snapshot["seat_version"],
            occupant_id=snapshot.get("occupant_id"),
            handoff_chain=list(snapshot.get("handoff_chain", [])),
            escalation_history=[dict(r) for r in snapshot.get("escalation_history", [])],
            outcome=snapshot.get("outcome"),
        )


@dataclass
class HandoffPacket:
    """Full state plus a signature. The signature covers the state, so a packet
    edited in transit fails verification instead of silently changing the work."""
    id: str
    task_id: str
    from_seat: str
    to_seat: str
    trigger: str
    snapshot: dict
    evidence_refs: list[str] = field(default_factory=list)
    signature: str = ""
    created_at: str = ""

    def body(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "from_seat": self.from_seat,
            "to_seat": self.to_seat,
            "trigger": self.trigger,
            "snapshot": self.snapshot,
            "evidence_refs": list(self.evidence_refs),
            "created_at": self.created_at,
        }

    def sign(self, key: bytes) -> "HandoffPacket":
        blob = canonical.canonical_bytes(self.body())
        self.signature = hmac.new(key, blob, hashlib.sha256).hexdigest()
        return self

    def verify(self, key: bytes) -> bool:
        blob = canonical.canonical_bytes(self.body())
        expected = hmac.new(key, blob, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)


# ---------------------------------------------------------------------------
# The runtime
# ---------------------------------------------------------------------------

class Workforce:
    def __init__(self, tenant_id: str, key: bytes, log=None,
                 revocation_poll_seconds: int = 5):
        if not key:
            raise WorkforceError("a signing key is required; there is no default")
        self.tenant_id = tenant_id
        self.key = key
        self.log = log
        self.revocation_poll_seconds = revocation_poll_seconds
        self.seats: dict[str, Seat] = {}
        self.occupants: dict[str, Occupant] = {}
        self.tasks: dict[str, Task] = {}
        self.packets: dict[str, HandoffPacket] = {}
        self.revoked_principals: set[str] = set()
        self.revocation_events: list[dict] = []

    # -- registration -----------------------------------------------------
    def register_seat(self, seat: Seat) -> Seat:
        seat.validate()
        self.seats[seat.id] = seat
        return seat

    def register_occupant(self, occupant: Occupant) -> Occupant:
        occupant.validate()
        if occupant.seat_id not in self.seats:
            raise WorkforceError(f"occupant {occupant.id!r} names an unknown seat")
        self.occupants[occupant.id] = occupant
        return occupant

    def occupants_of(self, seat_id: str) -> list[Occupant]:
        return [o for o in self.occupants.values() if o.seat_id == seat_id]

    # -- routing ----------------------------------------------------------
    def _terms(self, occupant: Occupant, seat: Seat, task: Task, now: datetime) -> dict:
        return {
            "capability_match": routing.metrics.capability_match(
                task.required_capabilities, seat.capability_manifest),
            "sla_headroom": routing.metrics.sla_headroom(
                task.sla_deadline, task.assigned_at, now),
            "trust_score": occupant.trust_score,
            "utilization": 1.0,  # one task per occupant in the reference runtime
            "cost_efficiency": 1.0,
            "escalation_penalty": 0.0,
        }

    def assign(self, task: Task, now: datetime | None = None) -> dict:
        """Route a task to an occupant of its seat. Returns the logged decision."""
        now = now or _now()
        seat = self.seats.get(task.seat_id)
        if seat is None:
            raise WorkforceError(f"task {task.id!r} names an unknown seat")

        if task.sla_deadline is None:
            task.sla_deadline = now + timedelta(seconds=seat.sla_seconds)
        if task.assigned_at is None:
            task.assigned_at = now
        task.seat_version = seat.version  # pinned at assignment

        candidates = []
        for occupant in self.occupants_of(seat.id):
            if occupant.status not in ("active", "shadow"):
                continue
            if self.is_revoked(occupant):
                continue
            candidates.append({
                "id": occupant.id,
                "status": "active",
                "terms": self._terms(occupant, seat, task, now),
                "estimated_cost": 0.0,
            })

        best = routing.select_occupant(candidates, version="workforce-v1")
        if best is None:
            task.state = "blocked"
            raise WorkforceError(f"no eligible occupant for seat {seat.id!r}")

        task.occupant_id = best["id"]
        task.state = "in_progress"
        self.tasks[task.id] = task

        if self.log:
            self.log.append(self.tenant_id, "system", "task.assigned",
                            {"task": task.id, "seat": seat.id, "occupant": best["id"],
                             "score": round(best["score"], 6),
                             "weights_version": best["weights_version"],
                             "breakdown": {k: round(v["contribution"], 6)
                                           for k, v in best["breakdown"].items()}},
                            canonical_ref=canonical.make_ref("Task", task.id))
        return best

    # -- escalation and handoff -------------------------------------------
    def escalate(self, task_id: str, trigger: str, evidence: list[str] | None = None,
                 now: datetime | None = None) -> HandoffPacket:
        """Move a task to the next seat on its ladder, carrying full state."""
        if trigger not in TRIGGERS:
            raise WorkforceError(f"unknown escalation trigger {trigger!r}")
        task = self.tasks.get(task_id)
        if task is None:
            raise WorkforceError(f"unknown task {task_id!r}")

        current = self.seats[task.seat_id]
        ladder = current.escalation_ladder
        if not ladder:
            raise WorkforceError(
                f"seat {current.id!r} declares no escalation_ladder; "
                "a task that cannot escalate must be parked explicitly"
            )

        next_seat_id = ladder[0]
        for index, seat_id in enumerate(ladder):
            if seat_id == current.id and index + 1 < len(ladder):
                next_seat_id = ladder[index + 1]
                break

        packet = HandoffPacket(
            id=canonical.uuid7(),
            task_id=task.id,
            from_seat=current.id,
            to_seat=next_seat_id,
            trigger=trigger,
            snapshot=task.snapshot(),
            evidence_refs=list(evidence or []),
            created_at=_iso(now or _now()),
        ).sign(self.key)

        self.packets[packet.id] = packet
        task.handoff_chain.append(packet.id)
        task.escalation_history.append({
            "packet": packet.id, "from": current.id, "to": next_seat_id,
            "trigger": trigger, "at": packet.created_at,
        })

        target = self.seats.get(next_seat_id)
        if target is None:
            raise WorkforceError(f"ladder names an unknown seat {next_seat_id!r}")

        # both clocks travel: the originating deadline and the receiving SLA
        task.escalation_history[-1]["originating_sla_seconds"] = current.sla_seconds
        task.escalation_history[-1]["receiving_sla_seconds"] = target.sla_seconds
        task.seat_id = target.id
        task.seat_version = target.version
        task.occupant_id = None
        task.state = "queued"

        if self.log:
            self.log.append(self.tenant_id, "system", "task.escalated",
                            {"task": task.id, "packet": packet.id, "trigger": trigger,
                             "from": current.id, "to": target.id,
                             "signature": packet.signature[:16]},
                            canonical_ref=canonical.make_ref("Task", task.id))
        return packet

    def receive(self, packet: HandoffPacket) -> Task:
        """Rebuild the task from the packet alone.

        Nothing else is consulted: not the task table, not the seat table. If the
        receiver needed more than the packet, the packet was a summary.
        """
        if not packet.verify(self.key):
            raise WorkforceError(
                f"packet {packet.id!r} failed signature verification; "
                "the state was altered in transit"
            )
        return Task.from_snapshot(packet.snapshot)

    def terminate(self, task_id: str, reason: str) -> Task:
        """End a ladder. Two terminal states, and the SLA behaves differently."""
        if reason not in (TERMINAL_PARKED, TERMINAL_HUMAN):
            raise WorkforceError(f"unknown terminal state {reason!r}")
        task = self.tasks[task_id]
        task.state = reason
        return task

    # -- revocation -------------------------------------------------------
    def revoke(self, principal_id: str, actor: str = "human") -> dict:
        """Revoke a principal. Every agent it holds stops at the next poll."""
        event = {
            "principal_id": principal_id,
            "at": _iso(_now()),
            "poll_seconds": self.revocation_poll_seconds,
        }
        self.revoked_principals.add(principal_id)
        self.revocation_events.append(event)
        if self.log:
            self.log.append(self.tenant_id, actor, "principal.revoked", event)
        return event

    def is_revoked(self, occupant: Occupant) -> bool:
        """Fail closed: an occupant whose principal is revoked cannot act."""
        return occupant.principal_id in self.revoked_principals

    def poll(self, occupant_id: str) -> bool:
        """What an agent checks before acting. True means it must stop."""
        occupant = self.occupants.get(occupant_id)
        if occupant is None:
            return True  # an unknown occupant fails closed too
        return self.is_revoked(occupant)

    # -- autonomy ---------------------------------------------------------
    def act(self, task_id: str, action: dict) -> dict:
        """Perform, discard or hold, according to the occupant's autonomy tier.

        shadow_only      computed, recorded, discarded. Nothing is applied.
        confirm_then_run held in the review queue until approved.

        The two are observably different, which is the whole point: in v1.0 of
        the specification both routed to the review queue and the tier field was
        decoration.
        """
        task = self.tasks[task_id]
        occupant = self.occupants.get(task.occupant_id or "")
        if occupant is None:
            raise WorkforceError(f"task {task_id!r} has no occupant")
        if self.poll(occupant.id):
            raise WorkforceError(
                f"occupant {occupant.id!r} is revoked and cannot act"
            )

        tier = occupant.autonomy_tier
        if tier == "shadow_only":
            result = {"tier": tier, "applied": False, "discarded": True,
                      "action": action, "task": task_id}
        elif tier == "confirm_then_run":
            result = {"tier": tier, "applied": False, "discarded": False,
                      "pending": True, "action": action, "task": task_id}
        else:
            raise WorkforceError(f"unknown autonomy tier {tier!r}")

        if self.log:
            self.log.append(self.tenant_id,
                            "agent" if occupant.type == "agent" else "human",
                            f"action.{tier}", result,
                            canonical_ref=canonical.make_ref("Task", task_id))
        return result

    def approve(self, task_id: str, proposal: dict, approver_id: str) -> dict:
        """A held action executes here, and an agent may not approve its own."""
        task = self.tasks[task_id]
        occupant = self.occupants.get(task.occupant_id or "")
        if occupant and occupant.id == approver_id and occupant.type == "agent":
            raise WorkforceError("an agent may not approve its own proposal")
        return {"tier": "confirm_then_run", "applied": True, "discarded": False,
                "approved_by": approver_id, "action": proposal.get("action"),
                "task": task_id}

    def complete(self, task_id: str, success: bool = True) -> Task:
        task = self.tasks[task_id]
        task.state = "done" if success else "failed"
        task.outcome = "success" if success else "failure"
        return task
