# 26 - Workforce

**Status: Draft**

Reference: [05-workforce.md](05-workforce.md). Deliverable 5.

The rule that separates this from a ticketing system: **work is assigned to a seat, never to a person**. A seat
is a versioned, machine-readable job description. A human or an agent occupies it. The router resolves which
occupant fills it, and the workflow layer never learns the answer.

## Four guarantees, enforced

| Guarantee | Where | Test |
|---|---|---|
| An agent seat cannot exist without a fallback seat | `Seat.validate()` | `test_agent_seat_without_fallback_is_rejected` |
| An escalation cannot exist without a full-state packet | `escalate()` | `test_escalation_builds_a_signed_packet` |
| A packet is signed, and the receiver rebuilds from it alone | `HandoffPacket`, `receive()` | `test_the_receiver_needs_nothing_but_the_packet` |
| Revoking a principal halts its agents, fail-closed | `revoke()`, `poll()`, `act()` | `test_revocation_halts_the_agent` |

The fourth is the one that matters most and is easiest to fake. `poll()` returns `True` for an unknown occupant
as well as a revoked one: an agent that cannot verify its principal's status cannot act.

## The packet is not a summary

```python
packet = wf.escalate(task_id, "low_confidence", evidence=["call-transcript-1"])
wf.tasks.clear(); wf.seats.clear(); wf.occupants.clear()
rebuilt = wf.receive(packet)     # works, because the packet carried everything
```

The test destroys the task table, the seat table and the occupant table before calling `receive()`. If the
receiver needed anything else, the packet was a summary and the escalation was a promise.

The signature is HMAC-SHA256 over the canonical serialisation of the packet body, including the snapshot. Edit
one field in transit and verification fails:

```python
packet.snapshot["payload"]["subject"] = "Something else entirely"
wf.receive(packet)      # WorkforceError: the state was altered in transit
```

There is no default key. A default key is not a signature, it is decoration.

## The two terminal states

An escalation ladder ends in exactly one of two places:

| Terminal state | Meaning | SLA clock |
|---|---|---|
| `parked` | Waiting for capacity | Pauses |
| `human_review_required` | Waiting for a named human | Continues |

There is no third. A task that can neither be parked nor handed to a human is a task nobody has thought about.

## Two clocks at every handoff

`escalation_history` records the originating SLA and the receiving seat's SLA. A task cannot expire against an
SLA the receiving seat never accepted, so both numbers travel and both are visible.

## Autonomy: two tiers that differ

The v1.0 specification said "shadow_only and confirm_then_run only" and also "all agent actions to review
queue", which made the two tiers identical. They are now observably different:

| Tier | What happens to the action | Result |
|---|---|---|
| `shadow_only` | Computed, recorded, discarded | `{"discarded": True, "applied": False}` |
| `confirm_then_run` | Held until approved | `{"pending": True, "applied": False}` |

An agent may not approve its own proposal. A human can.

## What is not here

- **No scheduler.** `assign()` is called by the caller. Nothing polls for queued work.
- **No revocation polling loop.** `poll()` is the check an agent makes; the 5-second interval is a configuration
  value and a stated target, not a running timer.
- **No queue persistence.** Tasks live in a dictionary. A restart loses them, which is why this is a reference
  runtime and not a deployment.
- **No capacity model.** `utilization` is hard-coded to 1.0 because one occupant holds one task here. The real
  term is in [10-metrics.md](10-metrics.md) and needs a load source.
- **No cost routing.** `cost_efficiency` is 1.0 for the same reason.

## Deliverable 5, updated

| Criterion | State |
|---|---|
| Task routes by documented score with a logged breakdown | Met |
| Agent seat rejected without `fallback_seat_id` | Met |
| Escalation rejected without a `HandoffPacket` | Met |
| Receiver reconstructs full state from the packet alone | Met |
| Seat version pinned at assignment | Met |
| Both SLA clocks recorded at handoff | Met |
| Autonomy tiers observably distinct | Met |
| Revocation halts the agent and fails closed | Met |
| Scheduler, persistence, capacity model | **Not met** - not part of the acceptance criterion, and not built |
