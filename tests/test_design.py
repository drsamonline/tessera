import unittest

from tessera import design


class TestContrast(unittest.TestCase):
    def test_the_wcag_reference_ratios(self):
        self.assertEqual(design.contrast("#000000", "#FFFFFF"), 21.0)
        self.assertEqual(design.contrast("#FFFFFF", "#FFFFFF"), 1.0)

    def test_a_known_pair(self):
        # #767676 on white is the canonical 4.54:1 AA boundary
        self.assertAlmostEqual(design.contrast("#767676", "#FFFFFF"), 4.54, places=2)

    def test_every_declared_pair_passes_aa_in_both_themes(self):
        self.assertEqual(design.check_all_contrast(), [])

    def test_a_failing_pair_is_reported(self):
        saved = design.TOKENS["dark"]["text_muted"]
        design.TOKENS["dark"]["text_muted"] = "#2A3038"
        try:
            problems = design.check_contrast("dark")
            self.assertTrue(any("secondary text" in p for p in problems))
        finally:
            design.TOKENS["dark"]["text_muted"] = saved

    def test_the_ratio_is_symmetric(self):
        self.assertEqual(design.contrast("#0B0D10", "#E8E6E1"),
                         design.contrast("#E8E6E1", "#0B0D10"))

    def test_a_bad_hex_is_refused(self):
        with self.assertRaises(ValueError):
            design.luminance("navy")


class TestTokens(unittest.TestCase):
    def test_the_tokens_are_consistent(self):
        self.assertEqual(design.check_tokens(), [])

    def test_two_themes_and_two_densities(self):
        self.assertEqual(set(design.TOKENS), {"dark", "light"})
        self.assertEqual(set(design.DENSITY), {"comfortable", "compact"})

    def test_every_token_is_a_hex_colour(self):
        for theme, tokens in design.TOKENS.items():
            for name, value in tokens.items():
                self.assertRegex(value, r"^#[0-9A-Fa-f]{6}$", f"{theme}/{name}")

    def test_both_themes_carry_the_same_names(self):
        self.assertEqual(set(design.TOKENS["dark"]), set(design.TOKENS["light"]))

    def test_the_type_scale_is_a_ratio_not_a_list(self):
        scale = design.TYPE_SCALE
        self.assertEqual(len(scale), len(design.TYPE_STEPS))
        for previous, current in zip(scale, scale[1:]):
            self.assertGreater(current, previous)
            self.assertAlmostEqual(current / previous, 1.25, places=1)

    def test_compact_is_a_multiplier_not_a_new_scale(self):
        comfortable = design.spacing("comfortable")
        compact = design.spacing("compact")
        self.assertEqual(comfortable, design.SPACING)
        self.assertEqual(len(compact), len(comfortable))
        for full, tight in zip(comfortable, compact):
            self.assertLessEqual(tight, full)

    def test_an_unknown_density(self):
        with self.assertRaises(ValueError):
            design.spacing("roomy")

    def test_motion_is_under_a_quarter_second(self):
        for name, milliseconds in design.MOTION.items():
            self.assertLessEqual(milliseconds, 250, name)


class TestComponents(unittest.TestCase):
    def test_every_component_is_covered(self):
        self.assertEqual(design.check_components(), [])

    def test_every_contrast_pair_names_real_tokens(self):
        for component in design.COMPONENTS:
            for pair in component["contrast_pairs"]:
                foreground, _, background = pair.partition("/")
                self.assertIn(foreground, design.TOKENS["dark"])
                self.assertIn(background, design.TOKENS["dark"])

    def test_an_interactive_component_without_a_default_is_reported(self):
        saved = design.COMPONENTS[0]
        design.COMPONENTS = (dict(saved, states=("hover", "focus")),) + design.COMPONENTS[1:]
        try:
            self.assertTrue(any("default" in p for p in design.check_components()))
        finally:
            design.COMPONENTS = (saved,) + design.COMPONENTS[1:]

    def test_a_toast_needs_no_default_state(self):
        toast = [c for c in design.COMPONENTS if c["name"] == "Toast"][0]
        self.assertNotIn("default", toast["states"])
        self.assertFalse(toast["interactive"])


class TestIcons(unittest.TestCase):
    def test_eighty_icons_or_more(self):
        self.assertGreaterEqual(len(design.ICONS), 80)
        self.assertEqual(design.check_icons(), [])

    def test_names_are_unique(self):
        names = [name for name, _ in design.ICONS]
        self.assertEqual(len(names), len(set(names)))

    def test_every_icon_renders_to_svg(self):
        for name in design.ICON_NAMES:
            svg = design.icon_svg(name)
            self.assertTrue(svg.startswith("<svg"))
            self.assertIn(f'viewBox="0 0 {design.GRID} {design.GRID}"', svg)
            self.assertIn("stroke=", svg)
            self.assertIn("fill=\"none\"", svg, "the set is stroked, not filled")
            self.assertTrue(svg.endswith("</svg>"))

    def test_no_icon_is_empty(self):
        for name, shapes in design.ICONS:
            self.assertTrue(shapes, name)

    def test_every_shape_is_on_the_grid(self):
        for name, shapes in design.ICONS:
            for shape in shapes:
                for value in shape[1:]:
                    if not isinstance(value, str):
                        self.assertGreaterEqual(float(value), 0, name)
                        self.assertLessEqual(float(value), design.GRID, name)

    def test_a_duplicate_icon_is_reported(self):
        design.ICONS = design.ICONS + (design.ICONS[0],)
        try:
            self.assertTrue(any("twice" in p for p in design.check_icons()))
        finally:
            design.ICONS = design.ICONS[:-1]

    def test_an_off_grid_shape_is_reported(self):
        design.ICONS = design.ICONS + (("rogue", (("circle", 40, 12, 3),)),)
        try:
            self.assertTrue(any("outside" in p for p in design.check_icons()))
        finally:
            design.ICONS = design.ICONS[:-1]

    def test_an_unknown_icon_raises(self):
        with self.assertRaises(KeyError):
            design.icon_svg("nope")

    def test_the_icons_cover_the_interface(self):
        for required in ("contact", "company", "deal", "search", "settings",
                         "handoff", "history", "chevron_down"):
            self.assertIn(required, design.ICON_NAMES)


class TestTheMatrix(unittest.TestCase):
    def test_the_matrix_is_well_formed(self):
        self.assertEqual(design.check_matrix(), [])

    def test_at_least_two_checks_are_automated(self):
        automated = [row for row in design.WCAG_MATRIX if row["automated"]]
        self.assertGreaterEqual(len(automated), 2)

    def test_the_manual_checks_are_honest_about_not_running(self):
        for row in design.WCAG_MATRIX:
            if not row["automated"]:
                self.assertIn("not run", row["status"], row["check"])


if __name__ == "__main__":
    unittest.main()
