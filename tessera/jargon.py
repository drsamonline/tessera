"""The jargon lint.

Reference: docs/07-experience.md (the jargon map) and docs/17-constraints.md, rule
17: "Do not leak internal terms into the interface. Lint blocks release."
Deliverable 12.

Thirteen internal terms, thirteen interface replacements, and one rule: a term
from the left column must not appear in a string a user reads.

The linter is deliberately coarse. It matches the term, allows the case where the
match is inside the approved replacement, and reports everything else for a human
to look at. A cleverer linter would have a suppression mechanism, and a
suppression mechanism is how a lint rule becomes a formality.

    python3 -m tessera.jargon          # exit 1 if anything leaks
"""

from __future__ import annotations

import re
import sys

# The map, verbatim from docs/07-experience.md. If these two disagree, one of them
# is a defect; `test_the_map_matches_the_document` compares them.
JARGON = {
    "Chain": "Workflow chain",
    "UniversalEvent": "Activity / Action",
    "Canonical schema": "Unified data model",
    "Federation mesh": "Workspace",
    "Seat": "Position",
    "Occupant": "Member",
    "HandoffPacket": "Context brief",
    "EscalationLadder": "Handoff rules",
    "Autonomy tier": "Trust level",
    "Shadow mode": "Training mode",
    "Relationship Velocity Score": "Relationship health",
    "Forecast Provenance Ledger": "How this was calculated",
    "Bi-temporal records": "History",
}

# Terms that are also ordinary English words, matched on a word boundary and
# case-insensitively. The rest are matched as written, because `Seat` in a
# sentence is a leak and `seat` in `owner_seat_id` is an identifier, not prose.
WORD_TERMS = {"Chain", "Seat", "Occupant"}

# Where a match is acceptable: the approved replacement contains the term.
ALLOW_INSIDE_REPLACEMENT = True


def _pattern(term: str) -> re.Pattern:
    if term in WORD_TERMS:
        return re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    return re.compile(rf"\b{re.escape(term)}\b")


def find_leaks(text: str) -> list[dict]:
    """Every internal term in `text` that is not part of its own replacement."""
    leaks = []
    for term, replacement in JARGON.items():
        for match in _pattern(term).finditer(text):
            if ALLOW_INSIDE_REPLACEMENT and replacement.lower() in text.lower():
                # the sentence already uses the approved wording; a substring of
                # it is not a leak
                continue
            leaks.append({
                "term": term,
                "replacement": replacement,
                "at": match.start(),
                "text": text[max(0, match.start() - 20):match.end() + 20],
            })
    return leaks


def scan(mapping: dict[str, str], where: str = "catalogue") -> list[str]:
    """Check every value in a key -> string mapping. Returns human-readable problems."""
    problems = []
    for key, text in mapping.items():
        for leak in find_leaks(text):
            problems.append(
                f"{where}[{key}]: {leak['term']!r} leaked into user-facing text "
                f"(use {leak['replacement']!r}) near: {leak['text']!r}"
            )
    return problems


def scan_catalogue() -> list[str]:
    """The shipped string catalogue, which is the thing the constraint is about."""
    from .locale import CATALOGUE
    problems = []
    for key, entry in CATALOGUE.items():
        for code, text in entry.items():
            for leak in find_leaks(text):
                problems.append(
                    f"catalogue[{key}][{code}]: {leak['term']!r} leaked "
                    f"(use {leak['replacement']!r})"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    problems = scan_catalogue()
    if not problems:
        print(f"JARGON OK - {len(JARGON)} terms, no leaks in the shipped catalogue")
        return 0
    print(f"JARGON LEAKS - {len(problems)} found")
    for problem in problems:
        print(f"  {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
