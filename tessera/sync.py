"""Local-first sync: one protocol, online or offline.

Deliverable 4. The claim being tested is narrow and testable:

    a client renders from its own store
    a write made offline reconciles on reconnect with no lost update
    concurrent mutations converge to one state, whatever order they arrive in
    the same protocol serves both cases

The mechanism is field-level last-writer-wins over a Lamport clock with a
replica-id tiebreak. That is a **total order**, which is what makes convergence
guaranteed rather than likely: two replicas applying the same set of operations
in different orders reach the same state, and there is a test that does exactly
that with a thousand operations.

Two things this deliberately does not do:

* It does not merge two values into one. Field-level LWW picks a winner. The
  losing write is not lost - it stays in the operation log, and the mesh's
  conflict resolver is where a human decides - but the replica state holds one
  value per field, because a UI has to render something.
* It does not pretend a clock is a fact. Lamport counters order causality, not
  wall time. Two replicas that never met can produce the same counter value, and
  the replica-id tiebreak settles it deterministically rather than correctly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import canonical


def _fingerprint(state: dict) -> str:
    blob = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
    return canonical.canonical_hash({"state": blob})


@dataclass(frozen=True)
class Op:
    """One field write. Immutable, and idempotent by `id`."""
    id: str
    replica_id: str
    ref: str
    field_name: str
    value: object
    lamport: int
    actor: str = "human"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "replica_id": self.replica_id, "ref": self.ref,
            "field": self.field_name, "value": self.value,
            "lamport": self.lamport, "actor": self.actor,
        }

    @classmethod
    def from_dict(cls, row: dict) -> "Op":
        return cls(id=row["id"], replica_id=row["replica_id"], ref=row["ref"],
                   field_name=row["field"], value=row["value"],
                   lamport=int(row["lamport"]), actor=row.get("actor", "human"))

    def wins_over(self, other: "Op") -> bool:
        """The total order: higher Lamport, then higher replica id."""
        if self.lamport != other.lamport:
            return self.lamport > other.lamport
        return self.replica_id > other.replica_id


@dataclass
class Replica:
    """A client. It is the source of truth for its own writes until it syncs."""

    replica_id: str
    state: dict = field(default_factory=dict)      # ref -> field -> (lamport, replica, value)
    outbox: list[Op] = field(default_factory=list)
    applied: set = field(default_factory=set)      # op ids, for idempotency
    clock: int = 0
    cursor: int = 0

    # -- local writes -----------------------------------------------------
    def set(self, ref: str, field_name: str, value, actor: str = "human") -> Op:
        """Write locally and immediately. The server is not consulted."""
        canonical.parse_ref(ref)
        self.clock += 1
        op = Op(id=canonical.uuid7(), replica_id=self.replica_id, ref=ref,
                field_name=field_name, value=value, lamport=self.clock, actor=actor)
        self._apply(op)
        self.outbox.append(op)
        return op

    # -- reading ----------------------------------------------------------
    def get(self, ref: str) -> dict:
        return {name: cell[2] for name, cell in self.state.get(ref, {}).items()}

    def record(self, ref: str) -> dict:
        """The record as a canonical payload, with the envelope it needs."""
        object_name, record_id = canonical.parse_ref(ref)
        payload = {"id": record_id, "tenant_id": "", "valid_from": "", "tx_time": "",
                   "consent_state": "pending", "lawful_basis": "legitimate_interest",
                   "purpose_id": "", "retention_policy_id": ""}
        payload.update(self.get(ref))
        return payload

    def fingerprint(self) -> str:
        return _fingerprint({ref: self.get(ref) for ref in sorted(self.state)})

    # -- merging ----------------------------------------------------------
    def _apply(self, op: Op) -> bool:
        """Apply one operation if it wins. Returns whether the state changed."""
        if op.id in self.applied:
            return False
        self.applied.add(op.id)
        self.clock = max(self.clock, op.lamport)

        cells = self.state.setdefault(op.ref, {})
        current = cells.get(op.field_name)
        if current is not None:
            current_op = Op(id="", replica_id=current[1], ref=op.ref,
                            field_name=op.field_name, value=current[2], lamport=current[0])
            if not op.wins_over(current_op):
                return False
        cells[op.field_name] = (op.lamport, op.replica_id, op.value)
        return True

    def pull(self, ops: list[Op]) -> int:
        """Apply remote operations in whatever order they arrive."""
        changed = 0
        for op in ops:
            if self._apply(op):
                changed += 1
        return changed

    def push(self) -> list[Op]:
        """Drain the outbox. The caller keeps them if the push fails."""
        ops, self.outbox = self.outbox, []
        return ops


class SyncServer:
    """The authority. Holds the operation log and hands out what a client missed.

    Every accepted operation is also written to the ledger, so the sync stream
    and the audit trail cannot disagree about what happened.
    """

    def __init__(self, tenant_id: str, log=None):
        self.tenant_id = tenant_id
        self.log = log
        self.ops: list[Op] = []
        self.seen: set[str] = set()

    def push(self, ops: list[Op]) -> int:
        """Accept operations, ignoring any already seen. Returns how many were new."""
        added = 0
        for op in ops:
            if op.id in self.seen:
                continue
            self.seen.add(op.id)
            self.ops.append(op)
            added += 1
            if self.log:
                self.log.append(
                    self.tenant_id, op.actor, "sync.op",
                    {"op": op.id, "field": op.field_name, "value": op.value,
                     "lamport": op.lamport, "replica": op.replica_id},
                    canonical_ref=op.ref, source_node_id=op.replica_id,
                )
        return added

    def pull(self, since: int = 0) -> tuple[list[Op], int]:
        """Everything after `since`, plus the new cursor."""
        return self.ops[since:], len(self.ops)


def sync(replica: Replica, server: SyncServer) -> dict:
    """The whole protocol. Push what is local, pull what is missing.

    Called the same way whether the client was offline for a second or a week:
    the outbox holds what it did, the cursor holds what it has seen.
    """
    pushed = replica.push()
    accepted = server.push(pushed)
    incoming, cursor = server.pull(replica.cursor)
    replica.pull(incoming)
    replica.cursor = cursor
    return {"pushed": len(pushed), "accepted": accepted,
            "pulled": len(incoming), "cursor": cursor,
            "pending": len(replica.outbox)}


def converge(replicas: list[Replica], server: SyncServer, rounds: int = 2) -> list[str]:
    """Sync every replica until nothing is pending. Returns the fingerprints.

    Two rounds are enough for a hub topology: round one publishes, round two
    delivers. A mesh topology needs more, and that is a network design question
    rather than a protocol one.
    """
    for _ in range(rounds):
        for replica in replicas:
            sync(replica, server)
    return [replica.fingerprint() for replica in replicas]
