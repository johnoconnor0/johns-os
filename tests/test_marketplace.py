from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
