# 05 - Workforce (Layer 2)

**Status: Frozen (v1 subset)**

Tasks are assigned to seats, never to users. Humans and agents are interchangeable occupants. The v1 subset is
now explicit. *(Closes A-03.)*

## Implemented

Seats, occupants, tasks, signed handoff packets, escalation ladders, both SLA clocks, the two autonomy tiers
and fail-closed revocation are implemented and tested: [26-workforce.md](26-workforce.md). The scheduler,
queue persistence and the capacity model are not.

## v1 object subset

v1 implements **Seat, Occupant, Task, HandoffPacket, EscalationLadder**. Deferred to v2: shift scheduling,
cost-aware routing, workforce analytics with provenance, reputation scoring. *(Assumption AS-04.)*

| Object | Fields |
|---|---|
| Seat | versioned, machine-readable role; `capability_manifest`, `permissions_scope`, `availability_window`, `sla`, `cost_budget`, `fallback_seat_id` (required for agent seats), `escalation_ladder` |
| Occupant | `type` (human, agent, hybrid), `principal_id`, `seat_id`, `status` (active, shadow, paused, off_shift), `autonomy_tier`, `trust_score` |
| Task | `seat_id`, `required_capabilities`, `payload`, `sla_deadline`, `state`, `seat_version` (pinned at assignment), `handoff_chain` (ordered list of packet ids) |
| HandoffPacket | `full_state_snapshot`, `evidence_refs`, `signature` |

*(Closes D-06: `handoff_chain` is an ordered list of packet ids.)*

## Routing

```
score = 0.35 * capability_match
      + 0.20 * sla_headroom
      + 0.20 * trust_score
      + 0.15 * utilization
      + 0.10 * cost_efficiency
      - 0.30 * escalation_penalty
```

Every term normalized to `[0,1]`. The router falls through to the fallback seat when the top candidate is
unavailable, over budget or below the trust floor. Every decision is logged with its term-by-term breakdown and
the weight-vector version.

## Fallback and escalation

- Every agent seat declares `fallback_seat_id` and cannot be created without it.
- Every seat declares an `escalation_ladder` with triggers: unavailable, over_budget, low_confidence,
  `sla_80pct`, `sla_breached`, blocked.
- Escalation ladders terminate in a declared state: **parked** (awaiting capacity) or
  **human_review_required** (awaiting a named human). The SLA clock pauses in parked and continues in
  human_review_required. *(Closes D-03.)*
- SLA is re-evaluated at handoff. The packet carries the originating SLA and the receiving seat's SLA, and both
  are recorded against the task. *(Closes D-04.)*
- A task is pinned to the seat version current at assignment. A later permission or capability change does not
  retroactively alter authority over work in progress. *(Closes D-05.)*
- A HandoffPacket carries full state, never a summary. An escalation without one is rejected.

## Autonomy

v1 ships two tiers, and they are observably different. *(Closes D-01.)*

| Tier | Behaviour | Where the action lands | Observable difference |
|---|---|---|---|
| `shadow_only` | The action is computed and recorded, then discarded. Nothing is written to the node | Shadow log only | Zero mutations; a shadow record exists |
| `confirm_then_run` | The action is computed and held. It executes on approval and not before | Review queue, then the node | A pending item exists until approved |

v2 adds `run_and_log` with deterministic promotion and demotion over outcome metrics. No machine learning in the
promotion rule. Every change is audited.

Agents cannot approve their own proposals, touch consent, or modify pipeline settings.

## Revocation

"Removing a human stops the agent instantly" was a claim without a mechanism. The mechanism is now specified.
*(Closes D-02.)*

- Revocation is a signed `RevocationEvent` appended to the ledger.
- Every agent occupant polls for revocation every 5 seconds and treats a missed poll of 15 seconds as revoked.
- An in-flight action aborts at its next checkpoint. A checkpoint is mandatory before any external write.
- The default is fail-closed: an agent that cannot verify its principal's status cannot act.
- Propagation is measured: time from event append to agent halt is a monitored metric with a p99 target of
  6 seconds.

## Automation framework

**Triggers:** event, schedule, webhook, `field_change`, `sla_timer`.
**Conditions:** expression language over canonical fields.
**Actions:** `create_task`, `assign_to_seat`, `assign_to_occupant`, `update_record`, `send_email`,
`send_notification`, `call_webhook`, `wait`, `branch`, `escalate`, `close_task`.

`assign_to_seat` is the only bridge to the workforce layer, and the workflow engine never knows an occupant's
type. AI-authored playbooks are proposals; a human approves them; they compile to a deterministic workflow with
no AI call on the execution path.
