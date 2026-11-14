# 37 - Learning and onboarding

**Status: Draft**

Reference: [08-learning.md](08-learning.md). Deliverable 14, and the onboarding flow in deliverable 19 that the
bootcamps end on.

The specification's claim is that a user goes from "what is this" to "I cannot work without this" without a
consultant. That is a teaching claim, so what is tested here is the **structure**, and the doc says so.

## What runs

| Artefact | Where | Checked |
|---|---|---|
| Four role bootcamps | `learning.BOOTCAMPS` | each ends at the activation event, each ≤ 10 minutes |
| Academy: five videos | `learning.ACADEMY` | each 2-5 minutes, each linked from a coach tip |
| Sandbox | `learning.SANDBOX` | linked from the coach |
| In-app coach | `learning.COACH` | every tip's message key exists in the catalogue |
| Glossary | `learning.GLOSSARY` | every term resolves to a shipped string, in all five locales |
| Email drip | `learning.DRIP` | day 0, 3, 7, 30, each with subject, body and goal |
| Persona changelog | `learning.persona_changelog` | entries split by role; unclassified ones stay visible |

`check_learning()` returns a list of problems rather than a boolean, and the test asserts it is empty.

## The glossary caught a real gap

The interface vocabulary is thirteen terms. The message catalogue carried **ten** of them: `Activity`,
`Unified data model`, `Workflow chain` and `History` had no `term.*` key, so the product could not say four of the
words it uses.

That is exactly what the cross-check is for. `test_every_interface_vocabulary_term_is_defined` compares the jargon
map's replacements against the glossary, and `check_learning()` fails if a glossary key is missing from the
catalogue. The four keys were added in all five locales, the jargon lint stayed clean, and the budgets held.

## Every bootcamp ends at the same place

| Role | Activation step |
|---|---|
| Solo founder | Open the unified view and find a contact |
| Sales rep | See one contact with its whole history |
| Admin | Open the unified view for one customer |
| Support | See the customer's history from every system |

Four different routes to one event, which is what [01-product.md](01-product.md) says the activation event is:
*"Connect two systems of different kinds and see one contact in the unified view with activity from both."*

`onboarding_flow(role)` returns the flow with its gate stated: **the flow is complete when the activation step
succeeds, not when the last step is clicked.**

## Deliverables, updated

| Criterion | State |
|---|---|
| 14: four role bootcamps each reach the activation event | Met - asserted per role |
| 14: five videos and the sandbox linked from the coach | Met |
| 14: every glossary term maps to a UI string key | Met - thirteen terms, five locales |
| 19: a 10-minute onboarding flow delivering the activation event | Met as structure - the flow and its gate exist; nothing renders it |

## What is not here

- **No interface.** A bootcamp is a list of steps; nothing highlights them, and no step is instrumented.
- **No videos.** Five entries with titles and durations. The files do not exist.
- **No email delivery.** Templates and a schedule. Nothing sends.
- **No community platform.** Named in the specification, not built.
- **No completion tracking.** Whether a user finished step three is not recorded anywhere.
