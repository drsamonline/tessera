import unittest

from tessera import automation
from tessera.automation import (
    Action, AutomationError, Context, Engine, Proposal, Trigger, Workflow, evaluate, parse,
)


class TestExpressions(unittest.TestCase):
    def test_equality(self):
        self.assertTrue(evaluate("stage == 'won'", {"stage": "won"}))
        self.assertFalse(evaluate("stage == 'won'", {"stage": "lost"}))

    def test_numeric_comparison(self):
        self.assertTrue(evaluate("amount_minor > 100000", {"amount_minor": 4500000}))
        self.assertFalse(evaluate("amount_minor > 100000", {"amount_minor": 5}))

    def test_all_operators(self):
        record = {"n": 5, "s": "hello world"}
        for text in ("n == 5", "n != 4", "n > 4", "n >= 5", "n < 6", "n <= 5",
                     "s contains 'world'", "s startswith 'hello'",
                     "s endswith 'world'", "'world' in s"):
            self.assertTrue(evaluate(text, record), text)

    def test_boolean_composition(self):
        record = {"stage": "won", "amount_minor": 200}
        self.assertTrue(evaluate("stage == 'won' and amount_minor > 100", record))
        self.assertFalse(evaluate("stage == 'won' and amount_minor > 1000", record))
        self.assertTrue(evaluate("stage == 'lost' or amount_minor > 100", record))
        self.assertTrue(evaluate("not stage == 'lost'", record))

    def test_parentheses_change_precedence(self):
        record = {"a": True, "b": False, "c": False}
        self.assertFalse(evaluate("a and b or c", record))
        self.assertTrue(evaluate("a and (b or c)", record) is False)
        self.assertTrue(evaluate("(a and b) or a", record))

    def test_and_binds_tighter_than_or(self):
        record = {"a": False, "b": True, "c": True}
        self.assertTrue(evaluate("a and b or c", record), "False and True, or True")

    def test_nested_field_access(self):
        self.assertTrue(evaluate("payload.channel == 'email'",
                                 {"payload": {"channel": "email"}}))

    def test_literals(self):
        self.assertTrue(evaluate("flag == true", {"flag": True}))
        self.assertTrue(evaluate("missing == null", {"missing": None}))
        self.assertTrue(evaluate("n == -3", {"n": -3}))
        self.assertTrue(evaluate("n == 1.5", {"n": 1.5}))

    def test_a_missing_field_is_an_error_not_a_false(self):
        with self.assertRaises(AutomationError):
            evaluate("nope == 1", {"stage": "won"})

    def test_type_mismatch_is_an_error(self):
        with self.assertRaises(AutomationError):
            evaluate("stage > 5", {"stage": "won"})

    def test_empty_condition_is_rejected(self):
        with self.assertRaises(AutomationError):
            parse("   ")

    def test_trailing_tokens_are_rejected(self):
        with self.assertRaises(AutomationError):
            parse("a == 1 b == 2")

    def test_unbalanced_parentheses(self):
        with self.assertRaises(AutomationError):
            parse("(a == 1")


class TestTheLanguageIsNotPython(unittest.TestCase):
    """A condition is data. Data does not get to call __import__."""

    def test_dunder_identifiers_are_refused(self):
        with self.assertRaises(AutomationError) as ctx:
            parse("__import__ == 1")
        self.assertIn("dunder", str(ctx.exception))

    def test_a_function_call_does_not_parse(self):
        with self.assertRaises(AutomationError):
            parse("open('/etc/passwd')")

    def test_attribute_traversal_is_limited_to_the_record(self):
        # dots walk the record, they do not reach the interpreter
        with self.assertRaises(AutomationError):
            evaluate("a.b.c == 1", {"a": {"b": {}}})

    def test_a_statement_does_not_parse(self):
        for hostile in ("import os", "lambda: 1", "1 if a else 2", "[x for x in y]"):
            with self.assertRaises(AutomationError, msg=hostile):
                parse(hostile)

    def test_deep_nesting_is_refused(self):
        with self.assertRaises(AutomationError):
            parse("(" * 40 + "a == 1" + ")" * 40)

    def test_the_module_has_no_ai_on_its_path(self):
        with open(automation.__file__, encoding="utf-8") as handle:
            source = handle.read().lower()
        for forbidden in ("openai", "anthropic", "llm", "embedding", "prompt("):
            self.assertNotIn(forbidden, source, f"{forbidden} appears on the execution path")


class TestTriggers(unittest.TestCase):
    def test_kind_must_match(self):
        trigger = Trigger("field_change")
        self.assertTrue(trigger.fires({"kind": "field_change"}))
        self.assertFalse(trigger.fires({"kind": "webhook"}))

    def test_match_narrows(self):
        trigger = Trigger("field_change", {"field": "stage"})
        self.assertTrue(trigger.fires({"kind": "field_change", "field": "stage"}))
        self.assertFalse(trigger.fires({"kind": "field_change", "field": "amount"}))

    def test_unknown_trigger(self):
        with self.assertRaises(AutomationError):
            Trigger("on_a_tuesday")


class TestProposals(unittest.TestCase):
    def workflow(self):
        return Proposal(
            id="p1", name="Escalate stale deals",
            trigger=Trigger("sla_timer", {"seat": "triage"}),
            actions=[Action("assign_to_seat", {"seat_id": "specialist"})],
            condition="amount_minor > 100000",
            author="agent",
        )

    def test_a_proposal_cannot_be_registered(self):
        engine = Engine()
        with self.assertRaises(AutomationError) as ctx:
            engine.register(self.workflow())
        self.assertIn("approved", str(ctx.exception))

    def test_an_author_cannot_approve_its_own_proposal(self):
        with self.assertRaises(AutomationError):
            self.workflow().compile(approved_by="agent")

    def test_a_human_approval_compiles(self):
        workflow = self.workflow().compile(approved_by="priya")
        self.assertIsInstance(workflow, Workflow)
        self.assertEqual(len(workflow.source_hash), 64)
        self.assertTrue(workflow.compiled)

    def test_an_empty_approval_is_refused(self):
        with self.assertRaises(AutomationError):
            self.workflow().compile(approved_by="")

    def test_a_bad_condition_fails_at_compile_time(self):
        bad = self.workflow()
        bad.condition = "amount_minor >"
        with self.assertRaises(AutomationError):
            bad.compile(approved_by="priya")

    def test_an_unknown_action_fails_at_construction(self):
        with self.assertRaises(AutomationError):
            Action("launch_missiles")


class TestEngine(unittest.TestCase):
    def engine(self, **handlers):
        context = Context(handlers)
        return Engine(context), context

    def test_a_matching_workflow_runs(self):
        engine, context = self.engine(update_record=lambda p: {"ok": True})
        engine.register(Workflow(
            id="w1", name="Stamp", trigger=Trigger("field_change", {"field": "stage"}),
            actions=[Action("update_record", {"field": "touched", "value": True})]))
        results = engine.fire({"kind": "field_change", "field": "stage",
                               "record": {"stage": "won"}})
        self.assertTrue(results[0]["ran"])
        self.assertEqual(context.calls[0]["verb"], "update_record")

    def test_a_non_matching_trigger_does_nothing(self):
        engine, context = self.engine()
        engine.register(Workflow(id="w1", name="x", trigger=Trigger("webhook"),
                                 actions=[Action("send_email")]))
        self.assertEqual(engine.fire({"kind": "field_change"}), [])
        self.assertEqual(context.calls, [])

    def test_a_failing_condition_skips_the_actions(self):
        engine, context = self.engine()
        engine.register(Workflow(
            id="w1", name="x", trigger=Trigger("event"),
            condition="amount_minor > 1000", actions=[Action("send_email")]))
        results = engine.fire({"kind": "event", "record": {"amount_minor": 5}})
        self.assertFalse(results[0]["ran"])
        self.assertEqual(context.calls, [])

    def test_the_condition_reads_the_record(self):
        engine, context = self.engine()
        engine.register(Workflow(
            id="w1", name="x", trigger=Trigger("event"),
            condition="stage == 'won'", actions=[Action("send_notification")]))
        engine.fire({"kind": "event", "record": {"stage": "won"}})
        self.assertEqual(len(context.calls), 1)

    def test_an_action_with_no_handler_is_recorded_as_not_performed(self):
        engine, _ = self.engine()
        engine.register(Workflow(id="w1", name="x", trigger=Trigger("event"),
                                 actions=[Action("call_webhook", {"url": "https://x"})]))
        result = engine.fire({"kind": "event", "record": {}})[0]
        self.assertFalse(result["actions"][0]["performed"])

    def test_assign_to_seat_is_the_bridge(self):
        engine, _ = self.engine()
        engine.register(Workflow(id="w1", name="x", trigger=Trigger("event"),
                                 actions=[Action("assign_to_seat", {"seat_id": "s1"})]))
        self.assertTrue(engine.assign_to_seat_only_bridge())

    def test_the_engine_never_names_an_occupant_type(self):
        with open(automation.__file__, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("occupant_type ==", source)


class TestValidation(unittest.TestCase):
    def test_a_good_workflow_has_no_problems(self):
        workflow = Workflow(id="w", name="n", trigger=Trigger("event"),
                            actions=[Action("close_task")], condition="a == 1")
        self.assertEqual(automation.validate_workflow(workflow), [])

    def test_no_actions(self):
        workflow = Workflow(id="w", name="n", trigger=Trigger("event"), actions=[])
        self.assertTrue(any("no actions" in p for p in automation.validate_workflow(workflow)))

    def test_a_proposal_is_not_a_workflow(self):
        proposal = Proposal(id="p", name="n", trigger=Trigger("event"),
                            actions=[Action("close_task")])
        problems = automation.validate_workflow(proposal)
        self.assertTrue(any("approve" in p for p in problems))

    def test_eleven_actions_are_declared_and_all_constructible(self):
        self.assertEqual(len(automation.ACTIONS), 11)
        for verb in automation.ACTIONS:
            self.assertEqual(Action(verb).verb, verb)

    def test_five_triggers_are_declared_and_all_fire(self):
        self.assertEqual(len(automation.TRIGGERS), 5)
        for kind in automation.TRIGGERS:
            self.assertTrue(Trigger(kind).fires({"kind": kind}), kind)
            self.assertFalse(Trigger(kind).fires({"kind": "something_else"}), kind)


if __name__ == "__main__":
    unittest.main()
