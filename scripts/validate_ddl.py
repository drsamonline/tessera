"""Parse the generated Postgres DDL with Postgres's own parser.

`store.validate()` is a structural check written with regexes. This is a different
and stronger question: is the SQL *valid Postgres syntax*, according to
libpg_query — the parser the server itself uses.

It still does not prove the DDL runs. Constraints, extensions, roles and
privileges are resolved by the server, not the parser. `docs/39-postgres.md`
keeps that distinction; this script makes the syntax half a fact instead of an
assumption.

Exit code 0 means every statement parsed. 1 means at least one did not.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from tessera import store  # noqa: E402


def statements(sql: str) -> list[str]:
    """Split on semicolons outside quotes. Good enough for generated DDL."""
    out, current, quoted = [], [], False
    for char in sql:
        if char == "'":
            quoted = not quoted
        if char == ";" and not quoted:
            text = "".join(current).strip()
            if text and not all(line.strip().startswith("--") or not line.strip()
                                for line in text.splitlines()):
                out.append(text + ";")
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        out.append(tail)
    return out


def main() -> int:
    try:
        import pglast
    except ImportError:
        print("pglast is not installed: pip install pglast", file=sys.stderr)
        return 2

    ddl = store.schema_ddl()
    parts = statements(ddl)
    failed = []
    for index, statement in enumerate(parts, start=1):
        try:
            pglast.parse_sql(statement)
        except Exception as exc:  # noqa: BLE001 - the parser raises several types
            failed.append((index, statement.splitlines()[0][:70], str(exc).splitlines()[0][:120]))

    tables = ddl.count("CREATE TABLE")
    policies = ddl.count("CREATE POLICY")
    print(f"pglast {pglast.__version__} · {len(parts)} statements · "
          f"{tables} tables · {policies} policies")
    if failed:
        print(f"FAILED — {len(failed)} statement(s) are not valid Postgres:")
        for index, head, message in failed:
            print(f"  #{index}: {head}\n      {message}")
        return 1
    print("OK — every statement parses as valid Postgres syntax")
    print("Not proven: that it runs. Constraints, extensions and privileges are "
          "resolved by the server, not the parser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
