#!/usr/bin/env python3
"""Inspect and validate the johns-os plugin marketplace."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "marketplace" / "catalog.json"


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected JSON object")
    return data


def require_keys(path: Path, data: dict[str, Any], keys: list[str]) -> list[str]:
    return [f"{path}: missing required key {key}" for key in keys if key not in data]


def catalog() -> dict[str, Any]:
    return load_json(CATALOG)


def plugin_record(entry: dict[str, Any]) -> dict[str, Any]:
    record = entry.get("record")
    if not isinstance(record, str) or not record:
        raise SystemExit(f"{CATALOG}: plugin entry missing record")
    return load_json(ROOT / record)


def all_plugins() -> list[dict[str, Any]]:
    return [plugin_record(entry) for entry in catalog().get("plugins", [])]


def find_plugin(plugin_id: str) -> dict[str, Any]:
    for plugin in all_plugins():
        if plugin.get("id") == plugin_id:
            return plugin
    raise SystemExit(f"plugin not found: {plugin_id}")


def plugin_summary(plugin: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": plugin.get("id"),
        "name": plugin.get("name"),
        "summary": plugin.get("summary"),
        "status": plugin.get("status"),
        "category": plugin.get("category"),
        "risk": plugin.get("risk"),
        "path": plugin.get("path"),
    }


def matches(plugin: dict[str, Any], query: str) -> bool:
    haystack = " ".join(
        [
            str(plugin.get("id", "")),
            str(plugin.get("name", "")),
            str(plugin.get("summary", "")),
            str(plugin.get("category", "")),
            " ".join(plugin.get("tags", [])),
            " ".join(plugin.get("capabilities", [])),
        ]
    ).lower()
    return query.lower() in haystack


def command_list(_: argparse.Namespace) -> int:
    print(json.dumps({"plugins": [plugin_summary(plugin) for plugin in all_plugins()]}, indent=2, sort_keys=True))
    return 0


def command_search(args: argparse.Namespace) -> int:
    found = [plugin_summary(plugin) for plugin in all_plugins() if matches(plugin, args.query)]
    print(json.dumps({"query": args.query, "matches": found}, indent=2, sort_keys=True))
    return 0


def command_show(args: argparse.Namespace) -> int:
    print(json.dumps(find_plugin(args.plugin_id), indent=2, sort_keys=True))
    return 0


def validate_catalog_shape(data: dict[str, Any]) -> list[str]:
    errors = require_keys(CATALOG, data, ["id", "name", "description", "version", "updated_at", "plugins"])
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        errors.append(f"{CATALOG}: plugins must be an array")
        return errors
    seen: set[str] = set()
    for index, entry in enumerate(plugins):
        if not isinstance(entry, dict):
            errors.append(f"{CATALOG}: plugins[{index}] must be an object")
            continue
        errors.extend(require_keys(CATALOG, entry, ["id", "record"]))
        plugin_id = entry.get("id")
        if isinstance(plugin_id, str):
            if plugin_id in seen:
                errors.append(f"{CATALOG}: duplicate plugin id {plugin_id}")
            seen.add(plugin_id)
        record = entry.get("record")
        if isinstance(record, str) and not (ROOT / record).exists():
            errors.append(f"{CATALOG}: record does not exist: {record}")
    return errors


def validate_plugin(plugin: dict[str, Any], record_path: Path) -> list[str]:
    required = [
        "id",
        "name",
        "summary",
        "status",
        "category",
        "version",
        "path",
        "manifest",
        "source",
        "capabilities",
        "tags",
        "risk",
        "install",
        "validation",
    ]
    errors = require_keys(record_path, plugin, required)
    plugin_path = ROOT / str(plugin.get("path", ""))
    manifest_path = ROOT / str(plugin.get("manifest", ""))
    if not plugin_path.is_dir():
        errors.append(f"{record_path}: plugin path does not exist: {plugin.get('path')}")
    if not manifest_path.is_file():
        errors.append(f"{record_path}: plugin manifest does not exist: {plugin.get('manifest')}")
    else:
        manifest = load_json(manifest_path)
        if manifest.get("name") != plugin.get("id"):
            errors.append(f"{record_path}: manifest name does not match plugin id")
        if manifest.get("version") != plugin.get("version"):
            errors.append(f"{record_path}: manifest version does not match plugin version")
        if manifest.get("homepage") != plugin.get("homepage"):
            errors.append(f"{record_path}: manifest homepage does not match plugin homepage")
    for key in ["capabilities", "tags"]:
        if not isinstance(plugin.get(key), list):
            errors.append(f"{record_path}: {key} must be an array")
    return errors


def validate_platform_surfaces(catalog_data: dict[str, Any]) -> list[str]:
    """Ensure platform marketplace manifests expose the same active plugins."""

    errors: list[str] = []
    expected = {
        entry.get("id")
        for entry in catalog_data.get("plugins", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }

    for path in [ROOT / "marketplace.json", ROOT / ".agents" / "plugins" / "marketplace.json"]:
        data = load_json(path)
        plugins = data.get("plugins", [])
        names = {entry.get("name") for entry in plugins if isinstance(entry, dict)}
        if names != expected:
            errors.append(f"{path}: plugin names do not match local catalog")
        for entry in plugins:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source")
            relative_path = source.get("path") if isinstance(source, dict) else None
            if not isinstance(relative_path, str) or not (ROOT / relative_path).is_dir():
                errors.append(f"{path}: plugin source path is missing for {entry.get('name')}")

    claude_path = ROOT / ".claude-plugin" / "marketplace.json"
    claude_data = load_json(claude_path)
    claude_plugins = claude_data.get("plugins", [])
    claude_names = {entry.get("name") for entry in claude_plugins if isinstance(entry, dict)}
    if claude_names != expected:
        errors.append(f"{claude_path}: plugin names do not match local catalog")
    for entry in claude_plugins:
        if not isinstance(entry, dict):
            continue
        plugin_id = entry.get("name")
        source = entry.get("source")
        source_path = ROOT / source if isinstance(source, str) else None
        if source_path is None or not source_path.is_dir():
            errors.append(f"{claude_path}: plugin source path is missing for {plugin_id}")
            continue
        manifest_path = source_path / ".claude-plugin" / "plugin.json"
        if not manifest_path.is_file():
            errors.append(f"{claude_path}: Claude manifest is missing for {plugin_id}")
            continue
        manifest = load_json(manifest_path)
        for key in ["version", "homepage"]:
            if entry.get(key) != manifest.get(key):
                errors.append(f"{claude_path}: {key} does not match manifest for {plugin_id}")
    return errors


def command_validate(_: argparse.Namespace) -> int:
    data = catalog()
    errors = validate_catalog_shape(data)
    errors.extend(validate_platform_surfaces(data))
    for entry in data.get("plugins", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("record"), str):
            continue
        record_path = ROOT / entry["record"]
        if record_path.exists():
            errors.extend(validate_plugin(load_json(record_path), record_path))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("johns-os marketplace is valid")
    return 0


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _set_version(path: Path, version: str, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing file, cannot set version: {path}")
        return
    data = load_json(path)
    data["version"] = version
    _write_json(path, data)


def command_bump_version(args: argparse.Namespace) -> int:
    """Set a plugin's version across every marketplace surface, then validate.

    Keeps the catalog record, both plugin manifests, and the Claude marketplace
    entry in lockstep so a release can never drift one surface again.
    """
    plugin_id = args.plugin_id
    version = args.version
    errors: list[str] = []
    data = catalog()
    record_rel = next((e.get("record") for e in data.get("plugins", []) if e.get("id") == plugin_id), None)
    if not isinstance(record_rel, str):
        raise SystemExit(f"plugin not found in catalog: {plugin_id}")
    record = load_json(ROOT / record_rel)
    plugin_path = str(record.get("path", ""))

    _set_version(ROOT / record_rel, version, errors)  # catalog record
    _set_version(ROOT / plugin_path / ".claude-plugin" / "plugin.json", version, errors)
    _set_version(ROOT / plugin_path / ".codex-plugin" / "plugin.json", version, errors)
    mp = ROOT / ".claude-plugin" / "marketplace.json"  # Claude marketplace entry
    if mp.is_file():
        mp_data = load_json(mp)
        for entry in mp_data.get("plugins", []):
            if entry.get("name") == plugin_id:
                entry["version"] = version
        _write_json(mp, mp_data)
    data["updated_at"] = datetime.now(UTC).strftime("%Y-%m-%dT00:00:00Z")  # refresh timestamp
    _write_json(CATALOG, data)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"bumped {plugin_id} to {version} across all marketplace surfaces")
    return command_validate(args)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    list_parser = sub.add_parser("list", help="List marketplace plugins.")
    list_parser.set_defaults(func=command_list)
    search_parser = sub.add_parser("search", help="Search marketplace plugins.")
    search_parser.add_argument("query")
    search_parser.set_defaults(func=command_search)
    show_parser = sub.add_parser("show", help="Show a plugin record.")
    show_parser.add_argument("plugin_id")
    show_parser.set_defaults(func=command_show)
    validate_parser = sub.add_parser("validate", help="Validate marketplace records.")
    validate_parser.set_defaults(func=command_validate)
    bump_parser = sub.add_parser("bump-version", help="Set a plugin's version across all marketplace surfaces.")
    bump_parser.add_argument("plugin_id")
    bump_parser.add_argument("version")
    bump_parser.set_defaults(func=command_bump_version)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
