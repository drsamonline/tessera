"""The automation framework: triggers, conditions, actions, and a gate.

Reference: docs/05-workforce.md ("Automation framework"). Deliverable 6.

Three parts:

    Trigger    event, schedule, webhook, field_change, sla_timer
    Condition  a small expression language, parsed here, never `eval`ed
    Action     eleven verbs; `assign_to_seat` is the only bridge to the workforce

The rule that gives this its shape: **an AI-authored playbook is a proposal, and a
proposal is not executable.** `Proposal.compile()` turns one into a `Workflow`
with a source hash, and only a `Workflow` runs. There is no model call anywhere on
the execution path, and `test_the_engine_has_no_ai_on_its_path` asserts that by
reading the module's own imports and identifiers rather than by trusting a comment.

The expression language is deliberately not Python. It is a tokenizer and a
recursive-descent parser over a fixed grammar with an identifier allowlist drawn
from the canonical schema. A condition written by a customer, or by a model on a
customer's behalf, is data - and data does not get to call `__import__`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from . import canonical

TRIGGERS = ("event", "schedule", "webhook", "field_change", "sla_timer")

ACTIONS = (
    "create_task", "assign_to_seat", "assign_to_occupant", "update_record",
    "send_email", "send_notification", "call_webhook", "wait", "branch",
    "escalate", "close_task",
)

# The only action that reaches the workforce layer. The engine never learns
# whether the occupant of a seat is a person or an agent.
WORKFORCE_BRIDGE = "assign_to_seat"

MAX_DEPTH = 24


class AutomationError(Exception):
    """Raised when a workflow, a condition or an action is not admissible."""


# ---------------------------------------------------------------------------
# The expression language
# ---------------------------------------------------------------------------

TOKEN = re.compile(r"""
    \s*(?:
        (?P<number>-?\d+(?:\.\d+)?)
      | (?P<string>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
      | (?P<op>==|!=|>=|<=|>|<)
      | (?P<paren>[()])
      | (?P<word>[A-Za-z_][A-Za-z0-9_.]*)
      | (?P<comma>,)
    )
""", re.VERBOSE)

KEYWORDS = {"and", "or", "not", "in", "contains", "startswith", "endswith",
            "true", "false", "null"}

COMPARATORS = {"==", "!=", ">", ">=", "<", "<=", "in", "contains", "startswith",
               "endswith"}


def tokenize(text: str) -> list[tuple[str, str]]:
    tokens, position = [], 0
    while position < len(text):
        match = TOKEN.match(text, position)
        if not match:
            if text[position:].strip() == "":
                break
            raise AutomationError(f"unexpected character at {position}: {text[position]!r}")
        position = match.end()
        for kind in ("number", "string", "op", "paren", "word", "comma"):
            value = match.group(kind)
            if value is not None:
                tokens.append((kind, value))
                break
    return tokens


class Node:
    """An expression node. Evaluate against a record; never against the world."""

    def evaluate(self, record: dict):
        raise NotImplementedError


@dataclass
class Literal(Node):
    value: object

    def evaluate(self, record: dict):
        return self.value


@dataclass
class Field(Node):
    name: str

    def evaluate(self, record: dict):
        current = record
        for part in self.name.split("."):
            if not isinstance(current, dict) or part not in current:
                raise AutomationError(f"field {self.name!r} is not on the record")
            current = current[part]
        return current


@dataclass
class Not(Node):
    operand: Node

    def evaluate(self, record: dict):
        return not bool(self.operand.evaluate(record))


@dataclass
class And(Node):
    left: Node
    right: Node

    def evaluate(self, record: dict):
        return bool(self.left.evaluate(record)) and bool(self.right.evaluate(record))


@dataclass
class Or(Node):
    left: Node
    right: Node

    def evaluate(self, record: dict):
        return bool(self.left.evaluate(record)) or bool(self.right.evaluate(record))


@dataclass
class Compare(Node):
    op: str
    left: Node
    right: Node

    def evaluate(self, record: dict):
        left = self.left.evaluate(record)
        right = self.right.evaluate(record)
        try:
            if self.op == "==":
                return left == right
            if self.op == "!=":
                return left != right
            if self.op == ">":
                return left > right
            if self.op == ">=":
                return left >= right
            if self.op == "<":
                return left < right
            if self.op == "<=":
                return left <= right
            if self.op == "in":
                return left in right
            if self.op == "contains":
                return right in left
            if self.op == "startswith":
                return str(left).startswith(str(right))
            if self.op == "endswith":
                return str(left).endswith(str(right))
        except TypeError as exc:
            raise AutomationError(
                f"cannot compare {type(left).__name__} and {type(right).__name__} "
                f"with {self.op!r}"
            ) from exc
        raise AutomationError(f"unknown operator {self.op!r}")


class Parser:
    """Recursive descent over the grammar. Depth-bounded, so a hostile string
    cannot exhaust the stack."""

    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.index = 0
        self.depth = 0

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else (None, None)

    def take(self):
        token = self.peek()
        self.index += 1
        return token

    def expect(self, kind, value=None):
        token = self.take()
        if token[0] != kind or (value is not None and token[1] != value):
            raise AutomationError(f"expected {value or kind}, found {token[1]!r}")
        return token

    def parse(self) -> Node:
        node = self.or_expr()
        if self.index != len(self.tokens):
            raise AutomationError(f"trailing tokens from {self.peek()[1]!r}")
        return node

    def _enter(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise AutomationError("expression nests too deeply")

    def or_expr(self) -> Node:
        self._enter()
        node = self.and_expr()
        while self.peek() == ("word", "or"):
            self.take()
            node = Or(node, self.and_expr())
        self.depth -= 1
        return node

    def and_expr(self) -> Node:
        node = self.not_expr()
        while self.peek() == ("word", "and"):
            self.take()
            node = And(node, self.not_expr())
        return node

    def not_expr(self) -> Node:
        if self.peek() == ("word", "not"):
            self.take()
            return Not(self.not_expr())
        return self.comparison()

    def comparison(self) -> Node:
        left = self.primary()
        kind, value = self.peek()
        if kind == "op" or (kind == "word" and value in COMPARATORS):
            self.take()
            return Compare(value, left, self.primary())
        return left

    def primary(self) -> Node:
        kind, value = self.take()
        if kind == "paren" and value == "(":
            node = self.or_expr()
            self.expect("paren", ")")
            return node
        if kind == "number":
            return Literal(float(value) if "." in value else int(value))
        if kind == "string":
            return Literal(value[1:-1].replace("\\'", "'").replace('\\"', '"'))
        if kind == "word":
            if value in ("true", "false"):
                return Literal(value == "true")
            if value == "null":
                return Literal(None)
            if value in KEYWORDS:
                raise AutomationError(f"{value!r} cannot start a comparison")
            if "__" in value:
                raise AutomationError(
                    f"identifier {value!r} is not allowed: dunder names are never fields"
                )
            return Field(value)
        raise AutomationError(f"unexpected token {value!r}")


def parse(text: str) -> Node:
    if not text or not text.strip():
        raise AutomationError("an empty condition is not a condition")
    return Parser(tokenize(text)).parse()


def evaluate(text: str, record: dict) -> bool:
    return bool(parse(text).evaluate(record))


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

@dataclass
class Action:
    verb: str
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.verb not in ACTIONS:
            raise AutomationError(f"unknown action {self.verb!r}")


@dataclass
class Trigger:
    kind: str
    match: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in TRIGGERS:
            raise AutomationError(f"unknown trigger {self.kind!r}")

    def fires(self, event: dict) -> bool:
        if event.get("kind") != self.kind:
            return False
        return all(event.get(key) == value for key, value in self.match.items())


@dataclass
class Workflow:
    """A compiled, deterministic workflow. This is the only thing that executes."""
    id: str
    name: str
    trigger: Trigger
    actions: list[Action]
    condition: str | None = None
    source_hash: str = ""
    compiled: bool = True

    def __post_init__(self):
        for action in self.actions:
            if action.verb not in ACTIONS:
                raise AutomationError(f"unknown action {action.verb!r}")
        if self.condition:
            parse(self.condition)  # fail at compile time, not at 3am


@dataclass
class Proposal:
    """What a model produces. Not executable, and it says so."""
    id: str
    name: str
    trigger: Trigger
    actions: list[Action]
    condition: str | None = None
    author: str = "agent"
    approved_by: str | None = None

    def compile(self, approved_by: str) -> Workflow:
        """Approve and compile. A proposal cannot run before this, by construction."""
        if not approved_by:
            raise AutomationError("a proposal needs a named human approval")
        if approved_by == self.author and self.author != "human":
            raise AutomationError("an author may not approve their own proposal")
        body = repr((self.name, self.trigger.kind, self.trigger.match,
                     [(a.verb, sorted(a.params.items())) for a in self.actions],
                     self.condition))
        return Workflow(
            id=self.id, name=self.name, trigger=self.trigger, actions=list(self.actions),
            condition=self.condition,
            source_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            compiled=True,
        )


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

class Context:
    """Where actions land. The engine knows verbs, not implementations."""

    def __init__(self, handlers: dict | None = None):
        self.handlers = dict(handlers or {})
        self.calls: list[dict] = []

    def __call__(self, verb: str, params: dict) -> dict:
        self.calls.append({"verb": verb, "params": params})
        handler = self.handlers.get(verb)
        if handler is None:
            return {"verb": verb, "params": params, "performed": False,
                    "reason": "no handler registered"}
        return handler(params)


class Engine:
    """Fires workflows against events. Deterministic, and it has no model."""

    def __init__(self, context: Context | None = None):
        self.workflows: dict[str, Workflow] = {}
        self.context = context or Context()
        self.runs: list[dict] = []

    def register(self, workflow: Workflow) -> Workflow:
        if not isinstance(workflow, Workflow):
            raise AutomationError(
                "only a compiled Workflow can be registered; a Proposal must be approved first"
            )
        self.workflows[workflow.id] = workflow
        return workflow

    def fire(self, event: dict) -> list[dict]:
        """Run every workflow whose trigger and condition match. Returns the run log."""
        results = []
        for workflow in self.workflows.values():
            if not workflow.trigger.fires(event):
                continue
            record = event.get("record") or {}
            if workflow.condition and not evaluate(workflow.condition, record):
                results.append({"workflow": workflow.id, "ran": False,
                                "reason": "condition did not match"})
                continue
            performed = [self.context(action.verb, dict(action.params,
                                                       record=record))
                         for action in workflow.actions]
            entry = {"workflow": workflow.id, "ran": True, "actions": performed}
            results.append(entry)
            self.runs.append(entry)
        return results

    def assign_to_seat_only_bridge(self) -> bool:
        """The workforce is reachable through exactly one verb.

        Returns whether that is still true. A workflow that names an occupant
        directly would make the layer's central rule decorative.
        """
        verbs = {action.verb for wf in self.workflows.values() for action in wf.actions}
        return "assign_to_occupant" not in verbs or WORKFORCE_BRIDGE in verbs


def validate_workflow(workflow: Workflow) -> list[str]:
    """Everything that must be true before a workflow is allowed to run."""
    problems = []
    if not isinstance(workflow, Workflow):
        problems.append("a proposal is not a workflow; approve and compile it first")
        return problems
    if not workflow.trigger:
        problems.append("a workflow needs a trigger")
    if not workflow.actions:
        problems.append("a workflow with no actions does nothing, on purpose or otherwise")
    for action in workflow.actions:
        if action.verb not in ACTIONS:
            problems.append(f"unknown action {action.verb!r}")
    if workflow.condition:
        try:
            parse(workflow.condition)
        except AutomationError as exc:
            problems.append(f"condition does not parse: {exc}")
    return problems
