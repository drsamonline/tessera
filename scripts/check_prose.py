"""Prose gates.

Documentation is the product here, and it is the one artefact no other check covers.
These are mechanical patterns, not style opinions: each one is a habit that makes
technical writing read as though nobody wrote it.

The budgets are measured from the corpus, not invented: 0.72 em dashes per thousand
words is what this repository produces when it is written carefully, so 1.2 is the
ceiling before it becomes the default connector.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = sorted((ROOT / "docs").glob("*.md")) + [ROOT / "README.md"]

BUDGETS = {
    "em dash per 1000 words": 1.2,
    "staged contrasts": 3,
    "closers of the form 'That is the X'": 0,
    "stock vocabulary": 0,
}

STOCK = re.compile(
    r"\b(genuinely|honestly|precisely|seamless|leverage|delve|tapestry|testament|"
    r"in today's fast-paced|unlock the power|game-chang\w+)\b", re.I)


def prose(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


def main() -> int:
    words = dashes = contrasts = closers = stock = 0
    offenders: list[tuple[str, int]] = []

    for path in FILES:
        text = prose(path.read_text(encoding="utf-8"))
        count = len(text.split())
        words += count
        d = text.count("\u2014")
        c = len(re.findall(r"\b(?:is|are|was|were) not [^.\n]{3,50}\.\s+(?:It|They|That) is", text))
        k = len(re.findall(r"That is the \w+", text))
        v = len(STOCK.findall(text))
        dashes += d
        contrasts += c
        closers += k
        stock += v
        if count > 150:
            offenders.append((path.name, d + c + k + v, count))

    per_thousand = dashes / words * 1000 if words else 0
    results = [
        ("em dash per 1000 words", per_thousand, BUDGETS["em dash per 1000 words"]),
        ("staged contrasts", contrasts, BUDGETS["staged contrasts"]),
        ("closers of the form 'That is the X'", closers, BUDGETS["closers of the form 'That is the X'"]),
        ("stock vocabulary", stock, BUDGETS["stock vocabulary"]),
    ]

    print(f"{words} words across {len(FILES)} files\n")
    failed = False
    for name, value, limit in results:
        over = value > limit
        failed = failed or over
        shown = f"{value:.2f}" if isinstance(value, float) else str(value)
        print(f"{'OVER' if over else 'ok  '}  {name:<38}{shown:>7}  (budget {limit})")

    offenders.sort(key=lambda row: row[1] / row[2], reverse=True)
    print("\ndensest files:")
    for name, hits, count in offenders[:5]:
        print(f"  {hits / count * 1000:5.1f} per 1000  {name:<32} {hits} in {count} words")

    if failed:
        print("\nFix by rewriting the sentence, not by deleting the claim.")
        return 1
    print("\nWithin budget.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
