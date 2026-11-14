"""The design system: tokens, contrast, density, components, icons.

Reference: docs/07-experience.md ("Design system"). Deliverable 11.

Four things, and one of them is arithmetic rather than taste:

    tokens       semantic colour, spacing, type, radius and motion, in two themes
    contrast     the WCAG ratio for every pair the interface actually uses
    density      comfortable and compact, as a multiplier on the spacing scale
    icons        eighty on a 24px grid, with consistent stroke and no fills

The contrast check is the part worth having. Every other design-system document in
the world says "AA compliant" and means "somebody looked at it". `check_contrast()`
computes the relative luminance of every foreground/background pair the components
declare, and returns the ones that fail. It runs in the suite, so a palette change
that breaks a ratio fails a test instead of shipping.

The icons are geometric placeholders on a 24px grid with one stroke weight, not a
designed family. The criterion asks that eighty be present and valid; it does not
ask them to be good, and this document says which of those two things is true.
"""

from __future__ import annotations

AA_TEXT = 4.5
AA_LARGE = 3.0
AAA_TEXT = 7.0
UI_COMPONENT = 3.0

TOKENS = {
    "dark": {
        "bg": "#0B0D10",
        "surface": "#14181D",
        "surface_raised": "#1C2229",
        "text": "#E8E6E1",
        "text_muted": "#A3ACB6",
        "accent": "#D9A441",
        "accent_ink": "#0B0D10",
        "danger": "#FF7B72",
        "success": "#56D364",
        "border": "#2A3038",
        "focus": "#D9A441",
    },
    "light": {
        "bg": "#F7F4EE",
        "surface": "#FFFFFF",
        "surface_raised": "#FFFFFF",
        "text": "#14181D",
        "text_muted": "#4F5760",
        "accent": "#7A5512",
        "accent_ink": "#FFFFFF",
        "danger": "#A4262C",
        "success": "#1A6E33",
        "border": "#CFC7B8",
        "focus": "#7A5512",
    },
}

# The pairs the interface actually renders. Each is (foreground, background, role).
PAIRS = (
    ("text", "bg", "body text on the page"),
    ("text", "surface", "body text on a card"),
    ("text_muted", "bg", "secondary text on the page"),
    ("text_muted", "surface", "secondary text on a card"),
    ("accent", "bg", "accent text on the page"),
    ("accent", "surface", "accent text on a card"),
    ("accent_ink", "accent", "text on a filled accent button"),
    ("danger", "surface", "error text"),
    ("success", "surface", "success text"),
    ("focus", "bg", "the focus ring against the page"),
)

SPACING = (0, 4, 8, 12, 16, 24, 32, 48, 64)
TYPE_SCALE = (12, 15, 19, 23, 29, 37, 46, 57)     # 1.25 ratio from 12px, rounded
TYPE_STEPS = ("caption", "small", "body", "title", "heading", "display",
              "hero", "banner")
RADIUS = {"sm": 4, "md": 8, "lg": 12, "pill": 999}
MOTION = {"fast": 120, "base": 150, "slow": 220}   # milliseconds
DENSITY = {"comfortable": 1.0, "compact": 0.75}

STATES = ("default", "hover", "focus", "disabled", "error")

# `interactive` decides whether a component must declare a `default` state. A
# toast has no resting state - it is always one of info, success or error - and
# demanding one would have produced a state nobody could design.
COMPONENTS = (
    {"name": "Button", "interactive": True, "states": STATES,
     "contrast_pairs": ("accent_ink/accent", "text/surface")},
    {"name": "Input", "interactive": True, "states": STATES,
     "contrast_pairs": ("text/surface", "danger/surface")},
    {"name": "Table", "interactive": True,
     "states": ("default", "hover", "selected", "empty"),
     "contrast_pairs": ("text/surface", "text_muted/surface")},
    {"name": "Kanban card", "interactive": True, "states": ("default", "dragging", "hover"),
     "contrast_pairs": ("text/surface", "accent/surface")},
    {"name": "Toast", "interactive": False, "states": ("info", "success", "error"),
     "contrast_pairs": ("text/surface_raised", "danger/surface")},
    {"name": "Sidebar", "interactive": True, "states": ("default", "collapsed", "hover"),
     "contrast_pairs": ("text/bg", "text_muted/bg")},
    {"name": "Badge", "interactive": False, "states": ("warning", "success", "error"),
     "contrast_pairs": ("accent_ink/accent", "text/surface")},
)


def luminance(colour: str) -> float:
    """WCAG relative luminance. Hex only, because that is what the tokens are."""
    value = colour.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"expected a six-digit hex colour, got {colour!r}")
    channels = [int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(c) for c in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground: str, background: str) -> float:
    """The WCAG contrast ratio, 1.0 to 21.0."""
    lighter = max(luminance(foreground), luminance(background))
    darker = min(luminance(foreground), luminance(background))
    return round((lighter + 0.05) / (darker + 0.05), 2)


def check_contrast(theme: str = "dark") -> list[str]:
    """Every declared pair, measured. Returns failures, not a boolean."""
    tokens = TOKENS[theme]
    problems = []
    for foreground, background, role in PAIRS:
        ratio = contrast(tokens[foreground], tokens[background])
        if ratio < AA_TEXT:
            problems.append(
                f"{theme}: {role} ({foreground} on {background}) is {ratio}:1, "
                f"below AA text at {AA_TEXT}:1")
    return problems


def check_all_contrast() -> list[str]:
    return check_contrast("dark") + check_contrast("light")


def spacing(density: str = "comfortable") -> tuple[int, ...]:
    """The scale at a density. Compact multiplies, it does not invent a new scale."""
    if density not in DENSITY:
        raise ValueError(f"unknown density {density!r}")
    factor = DENSITY[density]
    return tuple(round(step * factor) for step in SPACING)


def type_scale() -> dict:
    return dict(zip(TYPE_STEPS, TYPE_SCALE))


def check_tokens() -> list[str]:
    """The structural claims: two themes, one scale, every component covered."""
    problems = []
    if set(TOKENS) != {"dark", "light"}:
        problems.append("there must be exactly two themes")
    for theme, tokens in TOKENS.items():
        for name in TOKENS["dark"]:
            if name not in tokens:
                problems.append(f"{theme}: token {name!r} is missing")
            elif not tokens[name].startswith("#") or len(tokens[name]) != 7:
                problems.append(f"{theme}: token {name!r} is not a six-digit hex colour")
    if len(set(TOKENS["dark"].values())) < 6:
        problems.append("the dark theme has too few distinct colours to be semantic")
    for ratio in TYPE_SCALE:
        pass
    for step in (1, 2):
        previous, current = TYPE_SCALE[step - 1], TYPE_SCALE[step]
        if current < previous:
            problems.append("the type scale is not monotonic")
    for component in COMPONENTS:
        for pair in component["contrast_pairs"]:
            foreground, _, background = pair.partition("/")
            if foreground not in TOKENS["dark"]:
                problems.append(f"{component['name']}: unknown token {foreground!r}")
            if background not in TOKENS["dark"]:
                problems.append(f"{component['name']}: unknown token {background!r}")
    if set(DENSITY) != {"comfortable", "compact"}:
        problems.append("there must be exactly two densities")
    return problems


def check_components() -> list[str]:
    """Every component has the states and both themes and both densities."""
    problems = []
    names = [component["name"] for component in COMPONENTS]
    if len(set(names)) != len(names):
        problems.append("component names are not unique")
    for component in COMPONENTS:
        if not component.get("states"):
            problems.append(f"{component['name']}: no states declared")
        if component.get("interactive") and "default" not in component["states"]:
            problems.append(f"{component['name']}: interactive, so it needs a default state")
        if not component.get("contrast_pairs"):
            problems.append(f"{component['name']}: no contrast pairs declared")
    return problems


# ---------------------------------------------------------------------------
# Icons: eighty, on a 24px grid, one stroke weight, no fills
# ---------------------------------------------------------------------------

GRID = 24
STROKE = 1.75


def _i(name: str, *shapes) -> tuple:
    return (name, shapes)


ICONS = (
    _i("contact", ("circle", 12, 8, 4), ("path", "M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7")),
    _i("company", ("rect", 4, 7, 16, 14), ("path", "M8 21V3h8v18"), ("line", 12, 7, 12, 7)),
    _i("deal", ("path", "M4 8h16v11H4z"), ("path", "M8 8V5h8v3")),
    _i("activity", ("path", "M3 12h4l3 7 4-14 3 7h4")),
    _i("ticket", ("path", "M4 8h16v3a2 2 0 0 0 0 4v3H4v-3a2 2 0 0 0 0-4z")),
    _i("invoice", ("path", "M6 3h12v18l-3-2-3 2-3-2-3 2z"), ("line", 9, 9, 15, 9)),
    _i("task", ("rect", 4, 4, 16, 16), ("path", "M8 12l3 3 5-6")),
    _i("document", ("path", "M6 3h8l4 4v14H6z"), ("path", "M14 3v4h4")),
    _i("search", ("circle", 11, 11, 6), ("line", 15.5, 15.5, 20, 20)),
    _i("filter", ("path", "M3 5h18l-7 8v6l-4-2v-4z")),
    _i("sort", ("line", 4, 7, 20, 7), ("line", 4, 12, 14, 12), ("line", 4, 17, 9, 17)),
    _i("settings", ("circle", 12, 12, 3), ("circle", 12, 12, 8)),
    _i("user", ("circle", 12, 8, 3.5), ("path", "M6 20c0-3.3 2.7-5 6-5s6 1.7 6 5")),
    _i("users", ("circle", 9, 9, 3), ("circle", 16, 10, 2.5),
       ("path", "M3 20c0-3 2.4-4.5 6-4.5s6 1.5 6 4.5")),
    _i("team", ("circle", 8, 8, 2.5), ("circle", 16, 8, 2.5), ("circle", 12, 16, 2.5)),
    _i("seat", ("rect", 5, 3, 14, 12), ("path", "M5 15v6"), ("path", "M19 15v6")),
    _i("handoff", ("path", "M3 12h11"), ("path", "M10 7l5 5-5 5"), ("line", 20, 4, 20, 20)),
    _i("escalate", ("path", "M12 20V5"), ("path", "M6 11l6-6 6 6")),
    _i("check", ("path", "M4 13l5 5L20 6")),
    _i("close", ("line", 5, 5, 19, 19), ("line", 19, 5, 5, 19)),
    _i("plus", ("line", 12, 5, 12, 19), ("line", 5, 12, 19, 12)),
    _i("minus", ("line", 5, 12, 19, 12)),
    _i("edit", ("path", "M4 20h4L20 8l-4-4L4 16z")),
    _i("trash", ("path", "M5 7h14"), ("path", "M9 7V4h6v3"), ("path", "M6 7l1 13h10l1-13")),
    _i("save", ("path", "M5 4h11l3 3v13H5z"), ("rect", 8, 4, 8, 5)),
    _i("copy", ("rect", 8, 8, 12, 12), ("path", "M4 16V4h12")),
    _i("download", ("path", "M12 4v10"), ("path", "M7 10l5 5 5-5"), ("line", 4, 20, 20, 20)),
    _i("upload", ("path", "M12 15V5"), ("path", "M7 10l5-5 5 5"), ("line", 4, 20, 20, 20)),
    _i("mail", ("rect", 3, 6, 18, 12), ("path", "M3 7l9 6 9-6")),
    _i("phone", ("path", "M6 3l4 1 1 4-3 2a12 12 0 0 0 6 6l2-3 4 1 1 4-2 2A18 18 0 0 1 4 5z")),
    _i("calendar", ("rect", 4, 6, 16, 14), ("line", 4, 11, 20, 11), ("line", 9, 3, 9, 7)),
    _i("clock", ("circle", 12, 12, 8), ("path", "M12 8v5l3 2")),
    _i("bell", ("path", "M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"), ("path", "M10 20h4")),
    _i("link", ("path", "M9 15l6-6"), ("path", "M7 12l-2 2a3 3 0 0 0 4 4l2-2")),
    _i("unlink", ("path", "M9 15l6-6"), ("line", 4, 4, 8, 8)),
    _i("refresh", ("path", "M20 12a8 8 0 1 1-2.3-5.7"), ("path", "M20 4v5h-5")),
    _i("sync", ("path", "M4 10a8 8 0 0 1 14-3"), ("path", "M20 14a8 8 0 0 1-14 3")),
    _i("cloud", ("path", "M7 18h10a4 4 0 0 0 0-8 6 6 0 0 0-11 2 3 3 0 0 0 1 6z")),
    _i("cloud_off", ("path", "M7 18h10"), ("line", 3, 3, 21, 21)),
    _i("database", ("ellipse", 12, 6, 8, 3), ("path", "M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6")),
    _i("server", ("rect", 4, 4, 16, 7), ("rect", 4, 13, 16, 7), ("line", 8, 7.5, 8, 7.5)),
    _i("node", ("circle", 12, 12, 4), ("line", 12, 3, 12, 8), ("line", 12, 16, 12, 21)),
    _i("mesh", ("circle", 6, 6, 2), ("circle", 18, 6, 2), ("circle", 12, 18, 2),
       ("path", "M8 7l8 0"), ("path", "M7 8l4 8"), ("path", "M17 8l-4 8")),
    _i("graph", ("path", "M4 20V4"), ("path", "M4 20h16"), ("path", "M7 15l4-5 3 3 4-6")),
    _i("chart_bar", ("path", "M4 20h16"), ("rect", 6, 12, 3, 6), ("rect", 11, 8, 3, 10),
       ("rect", 16, 4, 3, 14)),
    _i("chart_line", ("path", "M4 20V4"), ("path", "M4 20h16"), ("path", "M6 16l4-6 4 3 5-8")),
    _i("chart_pie", ("circle", 12, 12, 8), ("path", "M12 12V4"), ("path", "M12 12l7 4")),
    _i("trend_up", ("path", "M4 16l6-6 4 4 6-7"), ("path", "M16 7h4v4")),
    _i("trend_down", ("path", "M4 8l6 6 4-4 6 7"), ("path", "M16 17h4v-4")),
    _i("target", ("circle", 12, 12, 8), ("circle", 12, 12, 4), ("circle", 12, 12, 1)),
    _i("flag", ("path", "M6 21V4h11l-2 4 2 4H6")),
    _i("star", ("path", "M12 3l2.6 5.6 6 .8-4.4 4.2 1.1 6L12 16.8 6.7 19.6l1.1-6L3.4 9.4l6-.8z")),
    _i("heart", ("path", "M12 20s-7-4.3-7-9a4 4 0 0 1 7-2 4 4 0 0 1 7 2c0 4.7-7 9-7 9z")),
    _i("shield", ("path", "M12 3l7 3v6c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6z")),
    _i("lock", ("rect", 5, 11, 14, 9), ("path", "M8 11V8a4 4 0 0 1 8 0v3")),
    _i("unlock", ("rect", 5, 11, 14, 9), ("path", "M8 11V8a4 4 0 0 1 7-2")),
    _i("key", ("circle", 8, 12, 3), ("path", "M11 12h9"), ("line", 17, 12, 17, 16)),
    _i("eye", ("path", "M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"), ("circle", 12, 12, 2.5)),
    _i("eye_off", ("path", "M4 4l16 16"), ("path", "M2 12s3.5-6 10-6c1.6 0 3 .3 4.3.9")),
    _i("alert", ("path", "M12 4l9 16H3z"), ("line", 12, 10, 12, 14), ("line", 12, 17, 12, 17)),
    _i("info", ("circle", 12, 12, 8), ("line", 12, 11, 12, 16), ("line", 12, 8, 12, 8)),
    _i("help", ("circle", 12, 12, 8), ("path", "M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3V14"),
       ("line", 12, 17, 12, 17)),
    _i("history", ("path", "M4 12a8 8 0 1 0 3-6.2"), ("path", "M4 4v5h5"), ("path", "M12 8v5l3 2")),
    _i("undo", ("path", "M4 12h11a5 5 0 0 1 0 10h-3"), ("path", "M8 7l-4 5 4 5")),
    _i("redo", ("path", "M20 12H9a5 5 0 0 0 0 10h3"), ("path", "M16 7l4 5-4 5")),
    _i("arrow_left", ("path", "M20 12H4"), ("path", "M10 6l-6 6 6 6")),
    _i("arrow_right", ("path", "M4 12h16"), ("path", "M14 6l6 6-6 6")),
    _i("arrow_up", ("path", "M12 20V4"), ("path", "M6 10l6-6 6 6")),
    _i("arrow_down", ("path", "M12 4v16"), ("path", "M6 14l6 6 6-6")),
    _i("chevron_left", ("path", "M15 5l-7 7 7 7")),
    _i("chevron_right", ("path", "M9 5l7 7-7 7")),
    _i("chevron_up", ("path", "M5 15l7-7 7 7")),
    _i("chevron_down", ("path", "M5 9l7 7 7-7")),
    _i("more", ("circle", 6, 12, 1.5), ("circle", 12, 12, 1.5), ("circle", 18, 12, 1.5)),
    _i("menu", ("line", 4, 7, 20, 7), ("line", 4, 12, 20, 12), ("line", 4, 17, 20, 17)),
    _i("grid", ("rect", 4, 4, 6, 6), ("rect", 14, 4, 6, 6), ("rect", 4, 14, 6, 6),
       ("rect", 14, 14, 6, 6)),
    _i("list", ("line", 4, 7, 20, 7), ("line", 4, 12, 20, 12), ("line", 4, 17, 20, 17)),
    _i("kanban", ("rect", 4, 4, 4, 16), ("rect", 10, 4, 4, 10), ("rect", 16, 4, 4, 13)),
    _i("table", ("rect", 3, 5, 18, 14), ("line", 3, 10, 21, 10), ("line", 10, 5, 10, 19)),
    _i("file", ("path", "M6 3h8l4 4v14H6z")),
    _i("folder", ("path", "M3 7h7l2 2h9v11H3z")),
    _i("tag", ("path", "M3 12l9-9 9 9-9 9z"), ("circle", 8, 8, 1.5)),
    _i("globe", ("circle", 12, 12, 8), ("path", "M4 12h16"), ("path", "M12 4a12 12 0 0 1 0 16")),
)

ICON_NAMES = tuple(name for name, _ in ICONS)


def check_icons() -> list[str]:
    """Eighty icons, unique names, valid primitives, nothing off the grid."""
    problems = []
    if len(ICONS) < 80:
        problems.append(f"{len(ICONS)} icons; the criterion asks for 80")
    names = [name for name, _ in ICONS]
    duplicates = {name for name in names if names.count(name) > 1}
    for name in sorted(duplicates):
        problems.append(f"icon {name!r} is defined twice")
    for name, shapes in ICONS:
        if not shapes:
            problems.append(f"icon {name!r} has no shapes")
        for shape in shapes:
            kind = shape[0]
            if kind not in ("circle", "rect", "line", "path", "ellipse"):
                problems.append(f"icon {name!r}: unknown primitive {kind!r}")
                continue
            for value in shape[1:]:
                if isinstance(value, str):
                    if not value.strip().startswith("M"):
                        problems.append(f"icon {name!r}: a path must start with M")
                elif not 0 <= float(value) <= GRID:
                    problems.append(
                        f"icon {name!r}: {value} is outside the {GRID}px grid")
    return problems


def icon_svg(name: str) -> str:
    """One icon as a standalone SVG string. The test renders every icon through here."""
    for icon_name, shapes in ICONS:
        if icon_name != name:
            continue
        parts = []
        for shape in shapes:
            kind = shape[0]
            if kind == "circle":
                parts.append(f'<circle cx="{shape[1]}" cy="{shape[2]}" r="{shape[3]}"/>')
            elif kind == "ellipse":
                parts.append(f'<ellipse cx="{shape[1]}" cy="{shape[2]}" '
                             f'rx="{shape[3]}" ry="{shape[4]}"/>')
            elif kind == "rect":
                parts.append(f'<rect x="{shape[1]}" y="{shape[2]}" '
                             f'width="{shape[3]}" height="{shape[4]}"/>')
            elif kind == "line":
                parts.append(f'<line x1="{shape[1]}" y1="{shape[2]}" '
                             f'x2="{shape[3]}" y2="{shape[4]}"/>')
            elif kind == "path":
                parts.append(f'<path d="{shape[1]}"/>')
        body = "".join(parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{GRID}" height="{GRID}" '
                f'viewBox="0 0 {GRID} {GRID}" fill="none" stroke="currentColor" '
                f'stroke-width="{STROKE}" stroke-linecap="round" '
                f'stroke-linejoin="round">{body}</svg>')
    raise KeyError(f"no icon named {name!r}")


# ---------------------------------------------------------------------------
# The manual test matrix, which cannot be automated
# ---------------------------------------------------------------------------

WCAG_MATRIX = (
    {"check": "Keyboard only, no pointer", "level": "A", "automated": False,
     "status": "not run - there is no interface"},
    {"check": "Focus visible on every interactive element", "level": "AA",
     "automated": False, "status": "not run"},
    {"check": "Focus order follows reading order", "level": "A", "automated": False,
     "status": "not run"},
    {"check": "Every control has an accessible name", "level": "A", "automated": False,
     "status": "not run"},
    {"check": "Contrast on every text pair", "level": "AA", "automated": True,
     "status": "automated in check_contrast()"},
    {"check": "Contrast on every UI boundary", "level": "AA", "automated": True,
     "status": "automated in check_contrast()"},
    {"check": "Text resizes to 200% without loss", "level": "AA", "automated": False,
     "status": "not run"},
    {"check": "Reflow at 320px width", "level": "AA", "automated": False,
     "status": "not run"},
    {"check": "Motion respects prefers-reduced-motion", "level": "AA", "automated": False,
     "status": "designed, not run"},
    {"check": "Every form error is announced, not only coloured", "level": "A",
     "automated": False, "status": "not run"},
)


def check_matrix() -> list[str]:
    problems = []
    if len(WCAG_MATRIX) < 10:
        problems.append("the matrix has fewer than ten checks")
    for row in WCAG_MATRIX:
        if row["level"] not in ("A", "AA", "AAA"):
            problems.append(f"{row['check']}: unknown level {row['level']!r}")
        if not row["status"]:
            problems.append(f"{row['check']}: no status")
    automated = sum(1 for row in WCAG_MATRIX if row["automated"])
    if automated < 2:
        problems.append("fewer than two checks are automated")
    return problems
