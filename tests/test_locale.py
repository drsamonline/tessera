import unittest
from datetime import datetime, timezone

from tessera import locale as L


class TestCatalogue(unittest.TestCase):
    def test_every_key_has_five_locales_within_budget(self):
        self.assertEqual(L.check_catalogue(), [])

    def test_the_jargon_map_is_the_interface_vocabulary(self):
        for key in ("term.connected_system", "term.workspace", "term.position",
                    "term.member", "term.context_brief", "term.handoff_rules",
                    "term.trust_level", "term.training_mode",
                    "term.relationship_health", "term.calculated"):
            self.assertIn(key, L.CATALOGUE, key)

    def test_a_missing_translation_is_reported(self):
        saved = dict(L.CATALOGUE["action.save"])
        del L.CATALOGUE["action.save"]["de"]
        try:
            problems = L.check_catalogue()
            self.assertTrue(any("action.save" in p and "de" in p for p in problems))
        finally:
            L.CATALOGUE["action.save"] = saved

    def test_an_overlong_translation_is_reported(self):
        saved = L.CATALOGUE["action.new"]
        L.CATALOGUE["action.new"] = dict(saved, de="Brandneuer Eintrag")
        try:
            problems = L.check_catalogue()
            self.assertTrue(any("exceeds" in p for p in problems))
        finally:
            L.CATALOGUE["action.new"] = saved

    def test_a_budget_for_a_key_that_does_not_exist_is_reported(self):
        L.BUDGETS["ghost.key"] = 10
        try:
            self.assertTrue(any("ghost.key" in p for p in L.check_catalogue()))
        finally:
            del L.BUDGETS["ghost.key"]


class TestTranslator(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(L.Translator("fr").t("action.save"), "Enregistrer")
        self.assertEqual(L.Translator("de").t("nav.contacts"), "Kontakte")

    def test_unknown_locale(self):
        with self.assertRaises(L.LocaleError):
            L.Translator("xx")

    def test_unknown_key(self):
        with self.assertRaises(L.LocaleError):
            L.Translator("en").t("nope.nope")

    def test_fallback_to_base(self):
        saved = L.CATALOGUE["action.save"]
        L.CATALOGUE["action.save"] = {"en": "Save"}
        try:
            self.assertEqual(L.Translator("de").t("action.save"), "Save")
        finally:
            L.CATALOGUE["action.save"] = saved

    def test_no_fallback_available_raises(self):
        saved = L.CATALOGUE["action.save"]
        L.CATALOGUE["action.save"] = {"fr": "Enregistrer"}
        try:
            with self.assertRaises(L.LocaleError):
                L.Translator("de").t("action.save")
        finally:
            L.CATALOGUE["action.save"] = saved

    def test_no_translation_is_ever_an_empty_string(self):
        for code in L.LOCALES:
            for key in L.CATALOGUE:
                self.assertTrue(L.Translator(code).t(key).strip(), f"{key}/{code}")


class TestFormatting(unittest.TestCase):
    def test_numbers_use_the_locale_separators(self):
        self.assertEqual(L.format_number(1234567, "en"), "1,234,567")
        self.assertEqual(L.format_number(1234567, "de"), "1.234.567")
        self.assertEqual(L.format_number(1234567, "fr"), "1 234 567")

    def test_decimals(self):
        self.assertEqual(L.format_number(1234.5, "en", decimals=2), "1,234.50")
        self.assertEqual(L.format_number(1234.5, "de", decimals=2), "1.234,50")

    def test_currency_is_minor_units(self):
        self.assertEqual(L.format_currency(4500000, "INR", "en"), "45,000.00 INR")
        self.assertEqual(L.format_currency(4500000, "EUR", "de"), "45.000,00 EUR")

    def test_currency_formatting_never_changes_the_value(self):
        for code in L.LOCALES:
            digits = "".join(c for c in L.format_currency(4500000, "EUR", code)
                             if c.isdigit())
            self.assertEqual(digits, "4500000", code)

    def test_dates_use_the_locale_order(self):
        moment = datetime(2026, 3, 14, 9, 0, tzinfo=timezone.utc)
        self.assertEqual(L.format_date(moment, "en", tz="UTC"), "14/03/2026")
        self.assertEqual(L.format_date(moment, "de", tz="UTC"), "14/03/2026")

    def test_the_timezone_shifts_the_date(self):
        late = datetime(2026, 3, 14, 20, 0, tzinfo=timezone.utc)
        self.assertEqual(L.format_date(late, "en", tz="UTC"), "14/03/2026")
        self.assertEqual(L.format_date(late, "en", tz="Asia/Kolkata"), "15/03/2026",
                         "20:00 UTC is the next day in Kolkata")

    def test_an_unknown_timezone(self):
        with self.assertRaises(L.LocaleError):
            L.format_date(datetime.now(timezone.utc), "en", tz="Mars/Olympus")

    def test_a_naive_datetime_is_read_as_utc(self):
        naive = datetime(2026, 3, 14, 9, 0)
        self.assertEqual(L.format_time(naive, tz="UTC"), "09:00")


class TestDirection(unittest.TestCase):
    def test_shipped_locales_are_ltr(self):
        for code in L.LOCALES:
            self.assertEqual(L.direction(code), "ltr")

    def test_the_mirror_locale_is_rtl(self):
        self.assertEqual(L.direction("ar-x-mirror"), "rtl")
        self.assertTrue(L.Translator("ar-x-mirror").rtl)

    def test_an_unknown_locale_is_ltr_not_an_error(self):
        self.assertEqual(L.direction("xx"), "ltr")

    def test_mirror_swaps_only_directional_tokens(self):
        tokens = {"paddingLeft": 8, "paddingRight": 4, "colour": "navy",
                  "alignStart": "left"}
        mirrored = L.mirror(tokens)
        self.assertEqual(mirrored["paddingRight"], 8)
        self.assertEqual(mirrored["paddingLeft"], 4)
        self.assertEqual(mirrored["colour"], "navy")
        self.assertEqual(mirrored["alignEnd"], "left")


class TestRates(unittest.TestCase):
    def setUp(self):
        self.table = L.RateTable()
        self.table.add("USD", "INR", 83.10, "2026-01-01")
        self.table.add("USD", "INR", 84.25, "2026-06-01")
        self.table.add("EUR", "INR", 90.00, "2026-01-01")

    def test_the_rate_on_the_transaction_date_is_used(self):
        self.assertEqual(self.table.rate_on("USD", "INR", "2026-03-14"), 83.10)
        self.assertEqual(self.table.rate_on("USD", "INR", "2026-07-01"), 84.25)

    def test_the_boundary_date_is_inclusive(self):
        self.assertEqual(self.table.rate_on("USD", "INR", "2026-06-01"), 84.25)

    def test_a_date_before_the_first_rate_is_an_error(self):
        with self.assertRaises(L.LocaleError):
            self.table.rate_on("USD", "INR", "2025-12-31")

    def test_an_unknown_pair_is_an_error(self):
        with self.assertRaises(L.LocaleError):
            self.table.rate_on("USD", "JPY", "2026-03-14")

    def test_the_same_currency_is_one(self):
        self.assertEqual(self.table.rate_on("INR", "INR", "2026-03-14"), 1.0)

    def test_conversion_is_in_minor_units_and_rounds(self):
        self.assertEqual(self.table.convert(100000, "USD", "INR", "2026-03-14"), 8310000)
        self.assertEqual(self.table.convert(100000, "USD", "INR", "2026-07-01"), 8425000)

    def test_a_non_positive_rate_is_refused(self):
        with self.assertRaises(L.LocaleError):
            self.table.add("USD", "INR", 0, "2027-01-01")

    def test_the_rate_does_not_drift_to_today(self):
        early = self.table.convert(100000, "USD", "INR", "2026-02-01")
        late = self.table.convert(100000, "USD", "INR", "2026-08-01")
        self.assertNotEqual(early, late, "two dates, two rates, two answers")


if __name__ == "__main__":
    unittest.main()
