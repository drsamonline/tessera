import os
import re
import shutil
import tempfile
import unittest

from tessera import jargon, plugins
from tessera.ledger import EventLog

TENANT = "018f0000-0000-7000-8000-000000000001"
KEY = b"plugin-key-not-a-secret"


class TestJargon(unittest.TestCase):
    def test_thirteen_terms(self):
        self.assertEqual(len(jargon.JARGON), 13)

    def test_the_map_matches_the_document(self):
        path = os.path.join(os.path.dirname(jargon.__file__), "..", "docs",
                            "07-experience.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        section = text.split("## Jargon map")[1].split("Architecture terms")[0]
        rows = [line for line in section.splitlines() if line.startswith("| ")]
        documented = {}
        for row in rows[2:]:
            cells = [c.strip() for c in row.strip("|").split("|")]
            documented[cells[0]] = cells[1]
        self.assertEqual(documented, jargon.JARGON,
                         "the linter and the document have drifted apart")

    def test_every_term_is_caught_in_a_fixture(self):
        for term in jargon.JARGON:
            leaks = jargon.find_leaks(f"Open the {term} panel")
            self.assertTrue(any(l["term"] == term for l in leaks),
                            f"{term!r} was not caught")

    def test_the_approved_replacement_is_not_a_leak(self):
        for replacement in jargon.JARGON.values():
            self.assertEqual(jargon.find_leaks(f"Showing: {replacement}"), [],
                             f"the replacement {replacement!r} was flagged")

    def test_a_leak_reports_the_replacement(self):
        leak = jargon.find_leaks("Seat assigned")[0]
        self.assertEqual(leak["replacement"], "Position")

    def test_ordinary_prose_is_clean(self):
        clean = ("Contacts, companies and deals. Search everything. "
                 "Nothing here yet. Save or cancel.")
        self.assertEqual(jargon.find_leaks(clean), [])

    def test_the_shipped_catalogue_has_no_leaks(self):
        self.assertEqual(jargon.scan_catalogue(), [])

    def test_a_leaking_catalogue_entry_is_reported(self):
        from tessera import locale
        saved = locale.CATALOGUE["action.save"]
        locale.CATALOGUE["action.save"] = dict(saved, de="Seat speichern")
        try:
            problems = jargon.scan_catalogue()
            self.assertTrue(any("action.save" in p for p in problems))
        finally:
            locale.CATALOGUE["action.save"] = saved

    def test_the_cli_exits_non_zero_on_a_leak(self):
        self.assertEqual(jargon.main(), 0)


class TestPlugins(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tessera-plugin-")
        self.log = EventLog(os.path.join(self.dir, "ledger.jsonl"))
        self.loader = plugins.Loader(KEY, allowlist={"clean"},
                                     granted_permissions={"email"}, log=self.log,
                                     tenant_id=TENANT)
        self.source = "def main(record):\n    return {'ok': True}\n"

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_clean_plugin_loads(self):
        plugin = plugins.build("clean", self.source, KEY)
        self.assertIs(self.loader.validate(plugin), plugin)
        self.assertIn("clean", self.loader.loaded)

    def test_an_unsigned_plugin_is_refused(self):
        plugin = plugins.build("clean", self.source, KEY)
        plugin.manifest.signature = ""
        with self.assertRaises(plugins.PluginError) as ctx:
            self.loader.validate(plugin)
        self.assertIn("unsigned", str(ctx.exception))

    def test_a_modified_source_is_refused(self):
        plugin = plugins.build("clean", self.source, KEY)
        plugin.source = self.source + "\n# tampered\n"
        with self.assertRaises(plugins.PluginError) as ctx:
            self.loader.validate(plugin)
        self.assertIn("pinned hash", str(ctx.exception))

    def test_a_forged_signature_is_refused(self):
        plugin = plugins.build("clean", self.source, b"another-key")
        with self.assertRaises(plugins.PluginError) as ctx:
            self.loader.validate(plugin)
        self.assertIn("signature", str(ctx.exception))

    def test_a_name_off_the_allowlist_is_refused(self):
        plugin = plugins.build("stranger", self.source, KEY)
        with self.assertRaises(plugins.PluginError) as ctx:
            self.loader.validate(plugin)
        self.assertIn("allowlist", str(ctx.exception))

    def test_a_denied_import_is_refused(self):
        for source in ("import os\n", "import subprocess\n", "from socket import socket\n"):
            plugin = plugins.build("clean", source, KEY)
            with self.assertRaises(plugins.PluginError, msg=source) as ctx:
                self.loader.validate(plugin)
            self.assertIn("denied", str(ctx.exception))

    def test_a_denied_call_is_refused(self):
        for source in ("eval('1')\n", "exec('x=1')\n", "open('/etc/passwd')\n",
                       "__import__('os')\n"):
            plugin = plugins.build("clean", source, KEY)
            with self.assertRaises(plugins.PluginError, msg=source):
                self.loader.validate(plugin)

    def test_a_permission_outside_the_grant_is_blocked_and_logged(self):
        plugin = plugins.build("clean", self.source, KEY, permissions=["network"])
        with self.assertRaises(plugins.PluginError) as ctx:
            self.loader.validate(plugin)
        self.assertIn("network", str(ctx.exception))
        refused = [e for e in self.log.events(TENANT) if e["action"] == "plugin.refused"]
        self.assertEqual(len(refused), 1)
        self.assertIn("network", refused[0]["payload"]["detail"])

    def test_a_granted_permission_is_allowed(self):
        plugin = plugins.build("clean", self.source, KEY, permissions=["email"])
        self.loader.validate(plugin)
        loaded = [e for e in self.log.events(TENANT) if e["action"] == "plugin.loaded"]
        self.assertEqual(len(loaded), 1)

    def test_an_unknown_permission_is_refused(self):
        plugin = plugins.build("clean", self.source, KEY, permissions=["telepathy"])
        with self.assertRaises(plugins.PluginError):
            self.loader.validate(plugin)

    def test_a_source_that_does_not_parse_is_refused(self):
        plugin = plugins.build("clean", "def broken(:\n", KEY)
        with self.assertRaises(plugins.PluginError) as ctx:
            self.loader.validate(plugin)
        self.assertIn("parse", str(ctx.exception))

    def test_a_loader_without_a_key_is_refused(self):
        with self.assertRaises(plugins.PluginError):
            plugins.Loader(b"")

    def test_every_refusal_is_logged(self):
        for source in ("import os\n", "eval('x')\n"):
            plugin = plugins.build("clean", source, KEY)
            with self.assertRaises(plugins.PluginError):
                self.loader.validate(plugin)
        refused = [e for e in self.log.events(TENANT) if e["action"] == "plugin.refused"]
        self.assertEqual(len(refused), 2)

    def test_the_loader_never_executes_the_plugin(self):
        marker = os.path.join(self.dir, "executed")
        source = f"open({marker!r}, 'w').write('x')\n"
        plugin = plugins.build("clean", source, KEY)
        with self.assertRaises(plugins.PluginError):
            self.loader.validate(plugin)
        self.assertFalse(os.path.exists(marker),
                         "validation must not run untrusted code")


if __name__ == "__main__":
    unittest.main()
