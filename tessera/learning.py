"""Learning: bootcamps, the academy, the coach, the glossary and the drip.

Reference: docs/08-learning.md. Deliverable 14, and the onboarding flow in
deliverable 19 that the bootcamps end on.

The specification's rule is that a user goes from "what is this" to "I cannot work
without this" without a consultant. That is a content claim, so what can be tested
here is the structure rather than the teaching:

    every role's bootcamp ends at the activation event
    the academy has five videos of 2-5 minutes and a sandbox, all reachable from the coach
    every glossary term resolves to a shipped interface string
    the drip has day 0, 3, 7 and 30, and every template names its message key

The third one is the one that catches drift. A glossary that defines a word the
interface does not use, or uses a word the glossary does not define, is a product
that explains itself in two vocabularies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import jargon, locale

ROLES = ("solo_founder", "sales_rep", "admin", "support")

# The activation event, from docs/01-product.md, as one sentence a bootcamp step
# can be measured against.
ACTIVATION = ("Connect two systems of different kinds and see one contact in the "
              "unified view with activity from both.")


@dataclass
class Step:
    title: str
    surface: str
    reaches_activation: bool = False


@dataclass
class Bootcamp:
    role: str
    steps: list[Step]
    minutes: int = 10

    @property
    def reaches_activation(self) -> bool:
        return any(step.reaches_activation for step in self.steps)

    @property
    def activation_step(self) -> Step | None:
        for step in self.steps:
            if step.reaches_activation:
                return step
        return None


BOOTCAMPS = {
    "solo_founder": Bootcamp("solo_founder", [
        Step("Create your workspace", "workspace"),
        Step("Connect the CRM you already use", "connected_system"),
        Step("Connect your support tool", "connected_system"),
        Step("Open the unified view and find a contact", "unified_view",
             reaches_activation=True),
        Step("Save a view you will use every morning", "saved_view"),
    ]),
    "sales_rep": Bootcamp("sales_rep", [
        Step("Find your pipeline", "pipeline"),
        Step("Connect your mail and calendar", "connected_system"),
        Step("See one contact with its whole history", "unified_view",
             reaches_activation=True),
        Step("Log an activity and watch it land", "activity"),
        Step("Ask for a handoff on a stalled deal", "handoff_rules"),
    ]),
    "admin": Bootcamp("admin", [
        Step("Invite the team and set positions", "positions"),
        Step("Connect the systems of record", "connected_system"),
        Step("Open the unified view for one customer", "unified_view",
             reaches_activation=True),
        Step("Read the audit trail for that customer", "history"),
        Step("Set a retention policy", "settings"),
    ]),
    "support": Bootcamp("support", [
        Step("Open your queue", "queue"),
        Step("Connect the helpdesk", "connected_system"),
        Step("See the customer's history from every system", "unified_view",
             reaches_activation=True),
        Step("Escalate with a context brief", "handoff_rules"),
        Step("Close the ticket and check the trail", "history"),
    ]),
}


@dataclass
class Video:
    id: str
    title: str
    seconds: int
    covers: tuple[str, ...]


ACADEMY = (
    Video("v1", "Connect your first system", 150, ("connected_system",)),
    Video("v2", "Read the unified view", 210, ("unified_view",)),
    Video("v3", "Log work and see the trail", 240, ("activity", "history")),
    Video("v4", "Hand off with a context brief", 180, ("handoff_rules",)),
    Video("v5", "Positions, members and trust", 300, ("positions", "trust_level")),
)

SANDBOX = {"id": "sandbox", "title": "A workspace with sample data",
           "reset": "one click", "writes": "discarded on reset"}


@dataclass
class Tip:
    surface: str
    text_key: str
    video: str | None = None


COACH = (
    Tip("unified_view", "term.data_model", "v2"),
    Tip("connected_system", "term.connected_system", "v1"),
    Tip("handoff_rules", "term.context_brief", "v4"),
    Tip("history", "term.history", "v3"),
    Tip("positions", "term.position", "v5"),
    Tip("saved_view", "term.workspace", "v2"),
    # the sandbox is reached from the coach the same way a video is; its id is the
    # one in SANDBOX, and check_learning asserts the link exists
    Tip("sandbox", "term.workspace", "sandbox"),
)

# The glossary is the jargon map's interface column: a term the user sees, and the
# message key that renders it. If a key here is not in the catalogue, the glossary
# defines a word the product cannot say.
GLOSSARY = {
    "Activity": "term.activity",
    "Context brief": "term.context_brief",
    "Handoff rules": "term.handoff_rules",
    "History": "term.history",
    "Member": "term.member",
    "Position": "term.position",
    "Relationship health": "term.relationship_health",
    "Training mode": "term.training_mode",
    "Trust level": "term.trust_level",
    "Unified data model": "term.data_model",
    "Workspace": "term.workspace",
    "Workflow chain": "term.workflow_chain",
    "How this was calculated": "term.calculated",
}

DRIP_DAYS = (0, 3, 7, 30)

DRIP = {
    0: {"subject_key": "drip.d0.subject", "body_key": "drip.d0.body",
        "goal": "connect one system"},
    3: {"subject_key": "drip.d3.subject", "body_key": "drip.d3.body",
        "goal": "reach the activation event"},
    7: {"subject_key": "drip.d7.subject", "body_key": "drip.d7.body",
        "goal": "save a view"},
    30: {"subject_key": "drip.d30.subject", "body_key": "drip.d30.body",
         "goal": "invite a colleague"},
}


def persona_changelog(entries: list[dict]) -> dict:
    """One changelog entry per persona, from one release note.

    `entries` are {"summary": str, "personas": [role, ...]}. A release that names
    no persona is reported as unclassified rather than dropped: an item nobody can
    find is an item nobody asked for.
    """
    out: dict[str, list[str]] = {role: [] for role in ROLES}
    out["unclassified"] = []
    for entry in entries:
        summary = entry.get("summary", "").strip()
        if not summary:
            continue
        personas = [p for p in entry.get("personas", []) if p in ROLES]
        if not personas:
            out["unclassified"].append(summary)
        for persona in personas:
            out[persona].append(summary)
    return out


def check_learning() -> list[str]:
    """Every structural claim in docs/08, checked. Returns problems, not a boolean."""
    problems = []

    for role in ROLES:
        bootcamp = BOOTCAMPS.get(role)
        if bootcamp is None:
            problems.append(f"{role}: no bootcamp")
            continue
        if not bootcamp.reaches_activation:
            problems.append(f"{role}: the bootcamp never reaches the activation event")
        if bootcamp.minutes > 10:
            problems.append(f"{role}: the bootcamp is {bootcamp.minutes} minutes, not 10")

    if len(ACADEMY) != 5:
        problems.append(f"the academy has {len(ACADEMY)} videos, not 5")
    for video in ACADEMY:
        if not 120 <= video.seconds <= 300:
            problems.append(f"{video.id}: {video.seconds}s is outside 2-5 minutes")

    linked = {tip.video for tip in COACH if tip.video}
    for video in ACADEMY:
        if video.id not in linked:
            problems.append(f"{video.id}: no coach tip links to this video")
    if not any(tip.surface == "sandbox" for tip in COACH):
        problems.append("no coach tip links to the sandbox")

    for tip in COACH:
        if tip.text_key not in locale.CATALOGUE:
            problems.append(f"coach tip on {tip.surface}: {tip.text_key} is not in the catalogue")

    for term, key in GLOSSARY.items():
        if key not in locale.CATALOGUE:
            problems.append(f"glossary term {term!r}: {key} is not in the catalogue")

    for day in DRIP_DAYS:
        entry = DRIP.get(day)
        if entry is None:
            problems.append(f"the drip has no day {day}")
            continue
        for key_field in ("subject_key", "body_key"):
            if not entry.get(key_field):
                problems.append(f"drip day {day}: no {key_field}")

    # the glossary and the interface vocabulary are the same list
    replacements = set(jargon.JARGON.values())
    glossary_terms = set(GLOSSARY)
    for replacement in replacements:
        primary = replacement.split(" / ")[0]
        if primary not in glossary_terms:
            problems.append(f"the glossary does not define {primary!r}, which the interface uses")

    return problems


def onboarding_flow(role: str) -> dict:
    """The 10-minute flow for one role, with the activation event as its gate."""
    bootcamp = BOOTCAMPS.get(role)
    if bootcamp is None:
        raise KeyError(f"unknown role {role!r}")
    return {
        "role": role,
        "minutes": bootcamp.minutes,
        "steps": [{"title": step.title, "surface": step.surface,
                   "activation": step.reaches_activation} for step in bootcamp.steps],
        "activation_event": ACTIVATION,
        "gate": "the flow is complete when the activation step succeeds, not when the last step is clicked",
    }
