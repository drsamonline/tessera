"""Verify the claims in CLAIMS.md that can be verified here.

A claim register that is never run is a list of assertions with a table drawn round it. This runs the checks that can
run in this environment and reports the ones that cannot, by name, rather than quietly skipping them.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(*args: str) -> tuple[int, str]:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def main() -> int:
    # 0 = pass, 1 = fail, 2 = cannot check here (a missing optional dependency is
    # not a failure and it is not a pass; saying which is the whole point)
    checks: list[tuple[str, int, str]] = []

    code, out = run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".")
    tests = re.search(r"Ran (\d+) tests", out)
    count = int(tests.group(1)) if tests else 0
    checks.append(("748 tests pass", 0 if code == 0 and count == 748 else 1,
                   f"{count} tests, exit {code}"))

    code, out = run(sys.executable, "scripts/conformance_report.py")
    checks.append(("four connectors, 16 checks each", code,
                   out.splitlines()[-1] if out else "no output"))

    code, out = run(sys.executable, "scripts/validate_ddl.py")
    if code == 2:
        checks.append(("DDL parses as Postgres", 2, "pglast not installed — pip install -r requirements-dev.txt"))
    else:
        checks.append(("DDL parses as Postgres", code,
                       next((l for l in out.splitlines() if l.startswith("OK")), out[:60])))

    code, out = run(sys.executable, "scripts/check_docs.py")
    checks.append(("documentation is fresh", code, out.splitlines()[0] if out else ""))

    code, out = run(sys.executable, "scripts/linkcheck.py")
    checks.append(("internal links resolve", code, out.splitlines()[0] if out else ""))

    register = (ROOT / "CLAIMS.md").read_text(encoding="utf-8")
    unverified = re.findall(r"^\| (\d+) \| (.+?) \| — \|", register, re.M)
    claims = len(re.findall(r"^\| \d+ \|", register, re.M))

    failures = [name for name, status, _ in checks if status == 1]
    skipped = [name for name, status, _ in checks if status == 2]
    for name, status, detail in checks:
        label = {0: "PASS", 1: "FAIL", 2: "SKIP"}[status]
        print(f"{label}  {name} — {detail}")
    print()
    print(f"{claims} claims registered, {len(unverified)} marked not verified:")
    for number, claim in unverified:
        print(f"  #{number}: {claim.strip()}")
    print()
    if failures:
        print(f"FAILED — {len(failures)} check(s) did not hold: {', '.join(failures)}")
        return 1
    if skipped:
        print(f"{len(skipped)} check(s) could not run here: {', '.join(skipped)}")
    print("Every check that can run here passed. The unverified claims are listed above, not hidden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
