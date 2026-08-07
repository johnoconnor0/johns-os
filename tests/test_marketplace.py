from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_PLUGINS = ["engineering-lifecycle", "business-development", "ai-utilities"]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class MarketplaceMetadataTests(unittest.TestCase):
    def test_active_plugin_manifests_and_records_are_complete(self) -> None:
        catalog = load(ROOT / "marketplace/catalog.json")
        records = {entry["id"]: load(ROOT / entry["record"]) for entry in catalog["plugins"]}
        self.assertEqual(set(records), set(ACTIVE_PLUGINS))
        for plugin_id in ACTIVE_PLUGINS:
            plugin_root = ROOT / plugin_id
            claude = load(plugin_root / ".claude-plugin/plugin.json")
            codex = load(plugin_root / ".codex-plugin/plugin.json")
            record = records[plugin_id]
            self.assertEqual(claude["name"], plugin_id)
            self.assertEqual(codex["name"], plugin_id)
            self.assertEqual(record["id"], plugin_id)
            self.assertEqual(record["version"], codex["version"])
            self.assertEqual(record["homepage"], "https://weblifter.com.au")

    def test_platform_marketplaces_list_the_same_active_plugins(self) -> None:
        codex_files = [ROOT / "marketplace.json", ROOT / ".agents/plugins/marketplace.json"]
        for path in codex_files:
            data = load(path)
            self.assertEqual({plugin["name"] for plugin in data["plugins"]}, set(ACTIVE_PLUGINS))
        claude = load(ROOT / ".claude-plugin/marketplace.json")
        self.assertEqual({plugin["name"] for plugin in claude["plugins"]}, set(ACTIVE_PLUGINS))

    def test_cli_installs_exactly_the_marketplace_plugins(self) -> None:
        # The npx installer advertises this marketplace. If it names a plugin the
        # marketplace does not declare, the failure only surfaces after a user has
        # already run the install.
        cli = load(ROOT / "cli/package.json")
        marketplace = load(ROOT / ".claude-plugin/marketplace.json")
        self.assertEqual(cli["version"], marketplace["version"])
        self.assertEqual(cli["bin"], {"johns-os": "index.js"})

        source = (ROOT / "cli/index.js").read_text(encoding="utf-8")
        declared = {plugin["name"] for plugin in marketplace["plugins"]}
        for name in ACTIVE_PLUGINS:
            if name in source:
                self.assertIn(name, declared, name)

        # Dependency-free on purpose: it runs via npx on unprepared machines.
        self.assertNotIn("dependencies", cli)

    def test_codex_interface_fields_are_never_present_but_blank(self) -> None:
        # Codex rejects interface.termsOfServiceURL / privacyPolicyURL when they
        # are provided but empty, so a blank string fails validation where an
        # absent key passes. Empty lists (screenshots) behave the same way.
        for plugin_id in ACTIVE_PLUGINS:
            interface = load(ROOT / plugin_id / ".codex-plugin/plugin.json").get("interface", {})
            for key, value in interface.items():
                with self.subTest(plugin=plugin_id, field=key):
                    if isinstance(value, str):
                        self.assertTrue(value.strip(), f"{plugin_id}: interface.{key} is empty; omit the key instead")
                    if isinstance(value, list):
                        self.assertTrue(value, f"{plugin_id}: interface.{key} is an empty list; omit the key instead")

    def test_public_metadata_has_website_and_no_runtime_workspace_in_marketplaces(self) -> None:
        for path in [ROOT / "marketplace.json", ROOT / ".agents/plugins/marketplace.json"]:
            for plugin in load(path)["plugins"]:
                self.assertNotIn(".project", plugin["source"]["path"])
        self.assertIn("https://weblifter.com.au", (ROOT / "README.md").read_text(encoding="utf-8"))


class SchemaEnforcementTests(unittest.TestCase):
    """The schemas beside the catalog are loaded, not decorative.

    `marketplace/schemas/*.schema.json` sat on disk unread while
    `johns-os-marketplace.py` hand-rolled a weaker `require_keys` that tested
    presence and never type, enum or format. The two drifted, exactly as you would
    expect: `homepage` was required by the schema and absent from the hand list.
    """

    def setUp(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import importlib.util  # noqa: PLC0415

        spec = importlib.util.spec_from_file_location("jos_marketplace", ROOT / "scripts" / "johns-os-marketplace.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def _plugin_schema(self) -> dict:
        return load(ROOT / "marketplace/schemas/plugin.schema.json")

    def test_the_schemas_are_actually_loaded(self) -> None:
        for name in ("catalog", "plugin"):
            self.assertTrue((ROOT / f"marketplace/schemas/{name}.schema.json").is_file())
        # A missing schema must be an error, not a silent pass — returning "no
        # errors" for an absent schema is how one comes to be ignored for months.
        self.assertTrue(self.module.schema_errors("does-not-exist", {}, "x"))

    def test_it_catches_what_presence_checking_could_not(self) -> None:
        record = load(ROOT / "marketplace/plugins/ai-utilities.json")
        schema = self._plugin_schema()
        self.assertEqual(self.module.validate_against_schema(record, schema, "ok"), [])

        for label, mutate in (
            ("enum", lambda d: d.update(risk="banana")),
            ("required", lambda d: d.pop("homepage", None)),
            ("type", lambda d: d.update(tags="not-a-list")),
            ("additionalProperties", lambda d: d.update(bogus_field=1)),
            ("minLength", lambda d: d.update(summary="")),
            ("format", lambda d: d.update(homepage="weblifter.com.au")),
        ):
            with self.subTest(rule=label):
                broken = json.loads(json.dumps(record))
                mutate(broken)
                self.assertTrue(self.module.validate_against_schema(broken, schema, "x"), label)

    def test_a_bool_is_not_an_integer(self) -> None:
        # `isinstance(True, int)` is True in Python and False in JSON Schema.
        self.assertTrue(self.module.validate_against_schema(True, {"type": "integer"}, "x"))
        self.assertEqual(self.module.validate_against_schema(3, {"type": "integer"}, "x"), [])

    def test_plugin_categories_agree_across_every_surface(self) -> None:
        # The same plugin was "Developer Tools" in three files and "engineering"
        # in its own catalog record. Version and homepage were cross-checked;
        # category simply was not, which is why it drifted.
        self.assertEqual(self.module.validate_categories(load(ROOT / "marketplace/catalog.json")), [])


class CliPackagingTests(unittest.TestCase):
    """What the published tarball contains, as opposed to what the checkout does.

    Every defect these cover shipped because the only smoke test ran
    `node cli/index.js` from the repository, where the parent directory and a
    newer Node are both available and neither is true of an npx install.
    """

    def setUp(self) -> None:
        self.package = load(ROOT / "cli/package.json")
        self.source = (ROOT / "cli/index.js").read_text(encoding="utf-8")

    def test_the_marketplace_manifest_index_reads_is_actually_packaged(self) -> None:
        # `files` cannot reference a parent directory, so reading the manifest
        # from `..` meant the published CLI always fell through to its hardcoded
        # fallback: stale descriptions, no version column, and a new plugin
        # invisible until someone hand-edited the fallback.
        self.assertIn("marketplace.json", self.source)
        self.assertIn("marketplace.json", self.package["files"])
        self.assertIn("marketplace.json", self.package.get("scripts", {}).get("prepack", ""))

    def test_the_declared_node_floor_supports_the_syntax_used(self) -> None:
        # `import.meta.dirname` needs Node 20.11. Under the old `>=18` floor it
        # was `undefined`, so `path.resolve` threw - taking down `list`,
        # `--version` and, because install with no names calls
        # marketplacePlugins(), the primary documented command as well.
        engines = str(self.package.get("engines", {}).get("node", ""))
        if "import.meta.dirname" in self.source:
            self.assertIn(">=20.11", engines, "import.meta.dirname requires Node >=20.11")

    def test_the_fallback_plugin_list_matches_the_marketplace(self) -> None:
        # The fallback is only reachable when both manifests are missing, which
        # makes it exactly the code nobody notices going stale.
        fallback = set(re.findall(r"name: '([a-z0-9-]+)'", self.source))
        self.assertEqual(fallback, set(ACTIVE_PLUGINS))

    def test_the_scopes_usage_advertises_are_the_ones_validated(self) -> None:
        # The usage text promised user|project|local while nothing checked the
        # value, so a typo reached `claude plugin install --scope <typo>` and a
        # trailing `--scope` reached it as the literal string "undefined".
        declared = re.search(r"const SCOPES = \[([^\]]+)\]", self.source)
        self.assertIsNotNone(declared, "cli/index.js should declare a SCOPES list")
        scopes = set(re.findall(r"'([a-z]+)'", declared.group(1)))
        self.assertEqual(scopes, {"user", "project", "local"})
        for scope in sorted(scopes):
            self.assertIn(scope, self.source.split("Usage:")[-1], f"usage text should advertise {scope}")


if __name__ == "__main__":
    unittest.main()
