import unittest

from tessera import jargon, learning, locale


class TestStructure(unittest.TestCase):
    def test_every_structural_claim_holds(self):
        self.assertEqual(learning.check_learning(), [])

    def test_four_roles(self):
        self.assertEqual(set(learning.BOOTCAMPS), set(learning.ROLES))
        self.assertEqual(len(learning.ROLES), 4)

    def test_every_bootcamp_reaches_the_activation_event(self):
        for role in learning.ROLES:
            bootcamp = learning.BOOTCAMPS[role]
            self.assertTrue(bootcamp.reaches_activation, role)
            self.assertIsNotNone(bootcamp.activation_step)

    def test_every_bootcamp_is_ten_minutes_or_less(self):
        for role in learning.ROLES:
            self.assertLessEqual(learning.BOOTCAMPS[role].minutes, 10)

    def test_a_bootcamp_that_misses_the_event_is_reported(self):
        saved = learning.BOOTCAMPS["admin"]
        learning.BOOTCAMPS["admin"] = learning.Bootcamp("admin", [
            learning.Step("Look around", "workspace")])
        try:
            problems = learning.check_learning()
            self.assertTrue(any("admin" in p and "activation" in p for p in problems))
        finally:
            learning.BOOTCAMPS["admin"] = saved


class TestAcademy(unittest.TestCase):
    def test_five_videos_between_two_and_five_minutes(self):
        self.assertEqual(len(learning.ACADEMY), 5)
        for video in learning.ACADEMY:
            self.assertGreaterEqual(video.seconds, 120)
            self.assertLessEqual(video.seconds, 300)

    def test_a_video_outside_the_window_is_reported(self):
        saved = learning.ACADEMY
        learning.ACADEMY = (learning.Video("v1", "Too long", 600, ("x",)),)
        try:
            problems = learning.check_learning()
            self.assertTrue(any("outside 2-5 minutes" in p for p in problems))
        finally:
            learning.ACADEMY = saved

    def test_the_sandbox_exists(self):
        self.assertEqual(learning.SANDBOX["id"], "sandbox")

    def test_every_video_is_linked_from_a_coach_tip(self):
        linked = {tip.video for tip in learning.COACH}
        for video in learning.ACADEMY:
            self.assertIn(video.id, linked)


class TestGlossary(unittest.TestCase):
    def test_every_term_resolves_to_a_shipped_string(self):
        for term, key in learning.GLOSSARY.items():
            self.assertIn(key, locale.CATALOGUE, term)
            self.assertTrue(locale.Translator("en").t(key).strip(), term)

    def test_every_interface_vocabulary_term_is_defined(self):
        replacements = {r.split(" / ")[0] for r in jargon.JARGON.values()}
        self.assertEqual(replacements - set(learning.GLOSSARY), set())

    def test_a_glossary_key_missing_from_the_catalogue_is_reported(self):
        learning.GLOSSARY["Ghost"] = "term.ghost"
        try:
            self.assertTrue(any("Ghost" in p for p in learning.check_learning()))
        finally:
            del learning.GLOSSARY["Ghost"]

    def test_the_glossary_renders_in_every_locale(self):
        for code in locale.LOCALES:
            for key in learning.GLOSSARY.values():
                self.assertTrue(locale.Translator(code).t(key).strip(), f"{key}/{code}")


class TestDrip(unittest.TestCase):
    def test_four_days(self):
        self.assertEqual(learning.DRIP_DAYS, (0, 3, 7, 30))
        self.assertEqual(set(learning.DRIP), {0, 3, 7, 30})

    def test_every_day_has_a_subject_and_a_body(self):
        for day, entry in learning.DRIP.items():
            self.assertTrue(entry["subject_key"], day)
            self.assertTrue(entry["body_key"], day)
            self.assertTrue(entry["goal"], day)

    def test_a_missing_day_is_reported(self):
        saved = dict(learning.DRIP)
        del learning.DRIP[7]
        try:
            self.assertTrue(any("day 7" in p for p in learning.check_learning()))
        finally:
            learning.DRIP.update(saved)


class TestChangelog(unittest.TestCase):
    def test_entries_are_split_by_persona(self):
        result = learning.persona_changelog([
            {"summary": "Faster search", "personas": ["sales_rep", "support"]},
            {"summary": "New retention setting", "personas": ["admin"]},
        ])
        self.assertEqual(result["sales_rep"], ["Faster search"])
        self.assertEqual(result["support"], ["Faster search"])
        self.assertEqual(result["admin"], ["New retention setting"])
        self.assertEqual(result["solo_founder"], [])

    def test_an_unclassified_entry_is_kept_visible(self):
        result = learning.persona_changelog([{"summary": "Something", "personas": []}])
        self.assertEqual(result["unclassified"], ["Something"])

    def test_an_empty_summary_is_dropped(self):
        result = learning.persona_changelog([{"summary": "  ", "personas": ["admin"]}])
        self.assertEqual(result["admin"], [])

    def test_an_unknown_persona_is_ignored_not_crashed(self):
        result = learning.persona_changelog([{"summary": "x", "personas": ["wizard"]}])
        self.assertEqual(result["unclassified"], ["x"])


class TestOnboarding(unittest.TestCase):
    def test_the_flow_names_the_activation_event(self):
        flow = learning.onboarding_flow("sales_rep")
        self.assertIn("unified view", flow["activation_event"])
        self.assertEqual(flow["minutes"], 10)

    def test_the_flow_has_an_activation_step(self):
        for role in learning.ROLES:
            flow = learning.onboarding_flow(role)
            self.assertTrue(any(step["activation"] for step in flow["steps"]), role)

    def test_an_unknown_role(self):
        with self.assertRaises(KeyError):
            learning.onboarding_flow("wizard")


if __name__ == "__main__":
    unittest.main()
