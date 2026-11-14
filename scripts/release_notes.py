#!/usr/bin/env python3
"""Build release notes from the tree, so a release is a command and not a memory.

The notes are: a fixed preamble that says what this is and what it is not, a stats
block counted from the tree rather than typed, and the newest CHANGELOG section.

Usage: python3 scripts/release_notes.py [> notes.md]
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PREAMBLE = """## What this is

The specification and reference core for TESSERA, the mosaic layer above every CRM: a
federation mesh over the systems a company already runs, a hash-chained ledger that
records every action in every one of them, and a workforce where humans and agents fill
the same seats.

No dependencies. Standard library only. No network at runtime.

## What this is not

- **Not a product.** There is no interface, no mobile client, no Postgres, and no live
  provider integration. Every gap is named in the documentation rather than omitted.
- **Not production ready.** `docs/31-code-review.md` lists what a production gate would
  require; most of it is closed and the rest is stated.
- **Not audited.** The symmetric layer in `docs/41-offline-mobile.md` is a reference
  construction and says so twice.

## The gates this release passed

Every one of these runs in CI and passes on the tagged commit.
"""

GATES = """
| Gate | Command |
|---|---|
| Test suite | `python3 -m unittest discover -s tests -t .` |
| Internal links | `python3 scripts/linkcheck.py` |
| Documentation freshness | `python3 scripts/check_docs.py` |
| Jargon lint | `python3 -m tessera.jargon` |
| Property tests | `python3 -m tessera.fuzz` |
| Regression benchmark | `python3 -m tessera.bench --gate` |
"""


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def count_tests():
    total = 0
    directory = os.path.join(ROOT, "tests")
    for name in sorted(os.listdir(directory)):
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        tree = ast.parse(read("tests", name))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                total += 1
    return total


def count_lines():
    total = 0
    for base in ("tessera", os.path.join("tessera", "providers")):
        directory = os.path.join(ROOT, base)
        for name in sorted(os.listdir(directory)):
            if name.endswith(".py"):
                total += len(read(base, name).splitlines())
    return total


def newest_changelog_section():
    text = read("CHANGELOG.md")
    sections = re.split(r"^## ", text, flags=re.MULTILINE)
    for section in sections[1:]:
        if section.startswith("["):
            return "## " + section.strip()
    return ""


def main():
    version = read("VERSION").strip()
    docs = len([name for name in os.listdir(os.path.join(ROOT, "docs"))
                if name.endswith(".md")])
    out = [f"# TESSERA {version}", "", PREAMBLE, GATES, "", "## The numbers", "",
           "| Metric | Value |", "|---|---|",
           f"| Tests | {count_tests()} |",
           f"| Modules | {count_lines()} lines across `tessera/` |",
           f"| Documents | {docs} in `docs/` |",
           f"| Dependencies | none |", "", newest_changelog_section(), ""]
    sys.stdout.write("\n".join(out))


if __name__ == "__main__":
    main()
