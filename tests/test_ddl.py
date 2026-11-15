"""The DDL is parsed by Postgres's own parser, not only by our regexes.

`store.validate()` answers "does it have the properties we promised". This answers
"is it valid Postgres at all". Both questions matter and neither is the other.
"""
import unittest

from tessera import store

try:
    import pglast
except ImportError:  # pragma: no cover - optional dependency
    pglast = None


@unittest.skipIf(pglast is None, "pglast is not installed")
class TestDdlParses(unittest.TestCase):
    def setUp(self):
        self.ddl = store.schema_ddl()

    def test_every_statement_parses(self):
        statements = [part.strip() for part in self.ddl.split(";") if part.strip()
                      and not part.strip().startswith("--")]
        self.assertGreater(len(statements), 40)
        for statement in statements:
            try:
                pglast.parse_sql(statement + ";")
            except Exception as exc:  # noqa: BLE001
                self.fail(f"not valid Postgres: {statement.splitlines()[0][:60]} — {exc}")

    def test_the_parser_rejects_a_broken_statement(self):
        """A check that cannot fail is not a check."""
        with self.assertRaises(Exception):
            pglast.parse_sql("CREATE TABLE nope (id uuid PRIMARY KEY,, );")

    def test_the_structural_validator_still_passes(self):
        self.assertEqual(store.validate(self.ddl), [])


if __name__ == "__main__":
    unittest.main()
