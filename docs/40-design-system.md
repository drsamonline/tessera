# 40 - Design system

**Status: Draft**

Reference: [07-experience.md](07-experience.md#design-system). Deliverable 11.

Four things, and one of them is arithmetic rather than taste.

| Part | Where | Checked |
|---|---|---|
| Tokens, two themes | `design.TOKENS` | every token is a six-digit hex; both themes carry the same names |
| Contrast | `design.check_contrast()` | every declared pair, measured, in both themes |
| Density | `design.spacing()` | compact is a multiplier on the scale, not a second scale |
| Components | `design.COMPONENTS` | states, contrast pairs, and a default where interactive |
| Icons | `design.ICONS` | 83 on a 24px grid, unique names, valid primitives |
| WCAG matrix | `design.WCAG_MATRIX` | ten checks, two automated, eight honest about not running |

## The contrast check is the part worth having

Every design-system document in the world says "AA compliant" and means "somebody looked at it". `check_contrast()`
computes the WCAG relative luminance of every foreground/background pair the components actually declare, and returns
the ones that fail.

```
design.contrast("#000000", "#FFFFFF")   # 21.0
design.contrast("#767676", "#FFFFFF")   # 4.54 - the canonical AA boundary
```

Ten pairs, both themes, twenty measurements, all above 4.5:1. The test that matters is the negative one: set
`text_muted` to a border colour and `test_a_failing_pair_is_reported` fails. A palette change that breaks a ratio
fails a test instead of shipping.

Both themes were adjusted to pass rather than declared to pass. The light accent is `#7A5512`, not the ochre the
dark theme uses, because the dark theme's `#D9A441` on a parchment background is 2.1:1.

## The type scale is a ratio, not a list

`12, 15, 19, 23, 29, 37, 46, 57` - a 1.25 ratio from 12px, rounded. The first version of this file had `12, 14, 16,
20, 25…`, which is a scale somebody eyeballed; the test that asserts every step is 1.25 caught it on the first run.

## Density is a multiplier

`spacing("compact")` multiplies the scale by 0.75 and keeps its length. A second hand-written scale is how two
layouts drift apart at the fifth breakpoint.

## Components declare what they render

Seven components, each with its states and the contrast pairs it uses. `interactive` decides whether a component
needs a `default` state: a Button does, a Toast does not - it is always info, success or error, and demanding a
resting state would have produced a state nobody could design.

## The icons are placeholders, and the doc says so

83 icons on a 24px grid, one stroke weight (1.75), no fills, primitives only - circles, rectangles, lines, paths.
`icon_svg()` renders each one and the test asserts every output is a well-formed SVG with the right viewBox.

They are **geometric placeholders, not a designed family.** The criterion asks that eighty be present and valid; it
does not ask them to be good. Both of those statements are true and only one of them is a compliment.

## The WCAG matrix is mostly not run

| Level | Checks | Automated |
|---|---|---|
| A | 4 | 0 |
| AA | 6 | 2 |
| Total | 10 | 2 |

Two are automated: contrast on text and on UI boundaries. The other eight - keyboard only, focus visible, focus
order, accessible names, 200% text, 320px reflow, reduced motion, announced errors - **need an interface**, and there
is none. `test_the_manual_checks_are_honest_about_not_running` asserts that every unautomated row says "not run" in
its status, so the matrix cannot quietly become a checklist of green ticks.

## Deliverable 11, updated

| Criterion | State |
|---|---|
| 80 icons present | Met - 83, validated |
| Every component has light, dark and both density modes | Met for tokens and density; components are specifications, not implementations |
| Contrast ratios measured and recorded per component | Met - twenty measurements, all passing, in the suite |
| WCAG 2.2 AA manual test matrix complete | **Partially met** - the matrix is complete as a document, 2 of 10 checks actually run |

## What is not here

- **No components.** Seven specifications with states and contrast pairs. No code renders a button.
- **No storybook, no visual regression.** Nothing to screenshot.
- **No icon export pipeline.** `icon_svg()` renders on demand; there is no sprite file and no build step.
- **No reduced-motion implementation.** The tokens exist and nothing consumes them.
- **No dark-mode switching logic.** Two token sets, no theme provider.
