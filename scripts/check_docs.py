#!/usr/bin/env python3
"""Docs freshness gate.

The rule this enforces: **every major push updates the documentation and the
landing page in the same commit.** A rule that lives in a habit is a rule that
survives until somebody is in a hurry, so it lives here instead and CI runs it.

Checks:
  1. the test count in README and on the landing page matches the tests that exist
  2. every numbered document is linked from docs/index.md
  3. every document linked from docs/index.md exists
  4. VERSION matches the newest CHANGELOG heading
  5. the document count on the landing page matches the documents that exist

Usage: python3 scripts/check_docs.py     exit 0 = fresh, 1 = stale
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNITS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
         "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
         "sixteen", "seventeen", "eighteen", "nineteen")
TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty",
        "ninety")


def number_word(value: int) -> str:
    """1 -> 'one', 38 -> 'thirty-eight'. The landing page spells its counts out."""
    if value < 20:
        return UNITS[value]
    tens, unit = divmod(value, 10)
    return TENS[tens] + (f"-{UNITS[unit]}" if unit else "")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def count_tests():
    """Every `def test_` in tests/. One method is one test in this suite."""
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


def numbered_docs():
    directory = os.path.join(ROOT, "docs")
    return sorted(name for name in os.listdir(directory)
                  if re.match(r"^\d\d-.*\.md$", name))


def main():
    problems = []
    tests = count_tests()

    readme = read("README.md")
    match = re.search(r"#\s*(\d+)\s*tests", readme)
    if not match:
        problems.append("README: no '# N tests' claim found")
    elif int(match.group(1)) != tests:
        problems.append(f"README says {match.group(1)} tests, the suite has {tests}")

    page = read("docs", "index.html")
    for label, pattern in (("badge", r"tests-(\d+)%20passing"),
                           ("text", r"(\d+) tests, standard library"),
                           ("under", r"under (\d+) tests")):
        found = re.search(pattern, page)
        if found and int(found.group(1)) != tests:
            problems.append(
                f"landing page {label} says {found.group(1)} tests, the suite has {tests}")

    docs = numbered_docs()
    index = read("docs", "index.md")
    for name in docs:
        if f"]({name})" not in index:
            problems.append(f"docs/index.md does not link {name}")
    for target in re.findall(r"\]\((\d\d-[^)#]+)\)", index):
        if target not in docs:
            problems.append(f"docs/index.md links {target}, which does not exist")

    version = read("VERSION").strip()
    changelog = read("CHANGELOG.md")
    newest = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    if not newest:
        problems.append("CHANGELOG.md has no version heading")
    elif newest.group(1) != version:
        problems.append(f"VERSION is {version}, the newest CHANGELOG entry is {newest.group(1)}")

    count_word = re.search(r"<h2>([A-Za-z-]+) documents\.", page)
    expected = number_word(len(docs) + 1)  # + index.md
    if not count_word:
        problems.append("landing page: no 'N documents' heading found")
    elif expected and count_word.group(1).lower() != expected:
        problems.append(
            f"landing page says {count_word.group(1)} documents, there are "
            f"{len(docs) + 1} including the index")

    if problems:
        print(f"DOCS STALE - {len(problems)} problem(s)")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"DOCS FRESH - {tests} tests, {len(docs) + 1} documents, version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
