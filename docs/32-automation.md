# 32 - Automation

**Status: Draft**

Reference: [05-workforce.md](05-workforce.md#automation-framework). Deliverable 6.

Three parts, and one rule that gives the whole thing its shape.

## The rule

**An AI-authored playbook is a proposal, and a proposal is not executable.**

```python
proposal = Proposal(id="p1", trigger=Trigger("sla_timer"), actions=[...], author="agent")
engine.register(proposal)                       # AutomationError: approve it first
workflow = proposal.compile(approved_by="priya")  # a Workflow, with a source hash
engine.register(workflow)                       # runs
```

`Engine.register` refuses anything that is not a compiled `Workflow`. A proposal cannot reach the execution path,
which is a stronger guarantee than a policy that says it should not.

Two smaller gates sit inside that one: an author may not approve its own proposal, and a condition that does not
parse fails at **compile** time rather than at three in the morning.

`test_the_module_has_no_ai_on_its_path` reads the module's own source and fails if `openai`, `anthropic`, `llm`,
`embedding` or a prompt call appears anywhere in it. That is a crude test, and it is the honest one: the claim is
about what is on the execution path, and the execution path is this file.

## The condition language is not Python

A condition is written by a customer, or by a model on a customer's behalf. It is data, and data does not get to
call `__import__`.

```
stage == 'won' and amount_minor > 100000
not (status == 'closed') or priority contains 'high'
payload.channel startswith 'ema'
```

Grammar: `or` over `and` over `not` over a comparison, with parentheses. Ten operators — `== != > >= < <= in
contains startswith endswith`. Identifiers walk the record with dots and nowhere else.

| Hostile input | Result |
|---|---|
| `__import__ == 1` | Refused: dunder identifiers are never fields |
| `open('/etc/passwd')` | Refused: no call syntax exists |
| `import os` | Refused: no statement syntax exists |
| `[x for x in y]` | Refused |
| `((((…40 deep…))))` | Refused: depth is bounded at 24 |

A missing field raises rather than evaluating false. A condition that silently passes because it misspelled a
field name is a workflow that quietly stops working, and nobody notices for a month.

## Triggers and actions

Five triggers: `event`, `schedule`, `webhook`, `field_change`, `sla_timer`. Each fires on its kind and narrows on
a match dict, so `field_change` with `{"field": "stage"}` does not fire on an amount change.

Eleven actions: `create_task`, `assign_to_seat`, `assign_to_occupant`, `update_record`, `send_email`,
`send_notification`, `call_webhook`, `wait`, `branch`, `escalate`, `close_task`. All eleven are declared, all
eleven construct, and an unknown verb fails at construction.

`assign_to_seat` is the only bridge to the workforce, and the engine never learns whether a seat's occupant is a
person or an agent. `test_the_engine_never_names_an_occupant_type` reads the source for exactly that.

## What is not here

- **No scheduler.** `schedule` and `sla_timer` are trigger kinds. Nothing ticks; a caller fires them.
- **No expression for arithmetic.** Conditions compare, they do not compute. `amount * 2 > 100` does not parse, on
  purpose: an arithmetic evaluator is a much larger attack surface than a comparator.
- **No `wait` duration handling.** `wait` is recorded as an action and does not pause anything, because pausing
  needs a scheduler.
- **No branch target resolution.** `branch` is recorded; the graph is not walked.
- **No dry-run.** `Engine.fire` performs. A `dry_run=True` mode that records what would have happened is the
  obvious next addition, and it is not there.
- **No persistence.** Workflows live in a dictionary.

## Deliverable 6, updated

| Criterion | State |
|---|---|
| All 5 triggers covered by tests | Met |
| All 11 actions covered by tests | Met - declared, constructible, dispatched |
| An AI-authored workflow is stored as a proposal and is non-executable until approved | Met - enforced in `Engine.register`, not in a policy |
| A dependency test asserts no AI call on the execution path | Met - the source scan, plus no such import exists |
| A scheduler that actually fires schedule and sla_timer triggers | **Not met** |
| `wait`, `branch` and dry-run semantics | **Not met** |
