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

    def test_public_metadata_has_website_and_no_runtime_workspace_in_marketplaces(self) -> None:
        for path in [ROOT / "marketplace.json", ROOT / ".agents/plugins/marketplace.json"]:
            for plugin in load(path)["plugins"]:
                self.assertNotIn(".project", plugin["source"]["path"])
        self.assertIn("https://weblifter.com.au", (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
