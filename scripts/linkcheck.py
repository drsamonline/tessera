#!/usr/bin/env python3
"""Relative-link checker for TESSERA markdown docs.

Scans every .md file under the repo root (excluding .git) and verifies that
relative link targets exist and code fences are balanced.
Usage: python3 scripts/linkcheck.py [root]
Exit code 0 = all links resolve; 1 = problems found.
"""
import os
import re
import sys


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    bad = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirpath:
            continue
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            base = os.path.dirname(p)
            text = open(p, encoding="utf-8").read()
            for m in re.finditer(r"\]\(([^)#\s]+)(#[^)]*)?\)", text):
                t = m.group(1)
                if t.startswith(("http://", "https://", "mailto:")):
                    continue
                q = os.path.normpath(os.path.join(base, t))
                if not os.path.exists(q):
                    bad.append(f"{p}: {t}")
            fences = text.count("```")
            if fences % 2:
                bad.append(f"{p}: UNBALANCED CODE FENCES ({fences})")
    if bad:
        print("BROKEN:")
        for b in bad:
            print(" ", b)
        return 1
    print("ALL INTERNAL LINKS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
