#!/usr/bin/env python3
"""Inspect and validate the johns-os plugin marketplace."""

from __future__ import annotations

import argparse
import json
import re
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


SCHEMAS = ROOT / "marketplace" / "schemas"

_JSON_TYPES: dict[str, tuple[type, ...] | type] = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
}


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    wanted = _JSON_TYPES.get(expected)
    if wanted is None:
        return True
    if expected in {"number", "integer"} and isinstance(value, bool):
        return False  # bool is an int in Python; JSON Schema disagrees
    return isinstance(value, wanted)


def validate_against_schema(value: Any, schema: dict[str, Any], label: str) -> list[str]:
    """The subset of JSON Schema these two schema files actually use.

    `type`, `required`, `properties`, `items`, `enum`, `minLength`, `format` and
    `additionalProperties: false`. Written out rather than taking a `jsonschema`
    dependency, because the CLI is dependency-free by design and the repository
    has avoided runtime dependencies everywhere else - and hand-rolling a
    *weaker* check was the actual defect: `require_keys` tested presence but
    never type, enum or format, so `risk: "banana"` passed.
    """
    errors: list[str] = []
    declared = schema.get("type")
    if isinstance(declared, str) and not _type_ok(value, declared):
        return [f"{label}: expected {declared}, got {type(value).__name__}"]
    if isinstance(declared, list) and not any(_type_ok(value, item) for item in declared):
        return [f"{label}: expected one of {declared}, got {type(value).__name__}"]

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{label}: {value!r} is not one of {schema['enum']!r}")
    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            errors.append(f"{label}: shorter than minLength {schema['minLength']}")
        if schema.get("format") == "uri" and value and not re.match(r"^[a-z][a-z0-9+.-]*:", value):
            errors.append(f"{label}: {value!r} is not a URI")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{label}: missing required key {key}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{label}: unexpected key {key}")
        for key, subschema in properties.items():
            if key in value and isinstance(subschema, dict):
                errors.extend(validate_against_schema(value[key], subschema, f"{label}.{key}"))
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            errors.extend(validate_against_schema(item, schema["items"], f"{label}[{index}]"))
    return errors


def schema_errors(name: str, value: Any, label: str) -> list[str]:
    """Validate against a schema file, and complain loudly if it is missing.

    Returning "no errors" for an absent schema is how a schema pair comes to sit
    on disk unread for months while a weaker hand-rolled check stands in for it.
    """
    path = SCHEMAS / f"{name}.schema.json"
    if not path.is_file():
        return [f"{path}: schema is missing"]
    return validate_against_schema(value, load_json(path), label)


def validate_catalog_shape(data: dict[str, Any]) -> list[str]:
    errors = schema_errors("catalog", data, str(CATALOG.relative_to(ROOT)))
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
    # The required-key list used to be re-declared here by hand, which is how it
    # drifted from the schema sitting beside it: `homepage` is required by the
    # schema and was absent from the hand-rolled list, and no value was ever
    # checked against an enum.
    errors = schema_errors("plugin", plugin, str(record_path.relative_to(ROOT)))
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


def validate_categories(catalog_data: dict[str, Any]) -> list[str]:
    """One plugin, one category, across every surface that names it.

    Nothing checked this, so the same plugin was `Developer Tools` in three files
    and `engineering` in its own catalog record. Version and homepage were already
    cross-checked; category simply was not, which is the whole reason it drifted.

    The four surfaces are still maintained separately on purpose (ADR-0001), so
    this compares them rather than generating one from another.
    """
    errors: list[str] = []
    surfaces = [
        ROOT / "marketplace.json",
        ROOT / ".agents" / "plugins" / "marketplace.json",
        ROOT / ".claude-plugin" / "marketplace.json",
    ]
    seen: dict[str, dict[str, str]] = {}
    for path in surfaces:
        for plugin in load_json(path).get("plugins", []):
            if isinstance(plugin, dict) and plugin.get("name"):
                seen.setdefault(plugin["name"], {})[str(path.relative_to(ROOT))] = str(plugin.get("category", ""))
    for entry in catalog_data.get("plugins", []):
        if not isinstance(entry, dict) or not entry.get("record"):
            continue
        record = load_json(ROOT / entry["record"])
        if record.get("id"):
            seen.setdefault(record["id"], {})[entry["record"]] = str(record.get("category", ""))

    for plugin_id, by_surface in sorted(seen.items()):
        values = set(by_surface.values())
        if len(values) > 1:
            detail = ", ".join(f"{where}={value!r}" for where, value in sorted(by_surface.items()))
            errors.append(f"{plugin_id}: category disagrees across surfaces ({detail})")
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


def validate_codex_interfaces(catalog_data: dict[str, Any]) -> list[str]:
    """Reject Codex `interface` fields that are present but blank.

    Codex rejects `interface.termsOfServiceURL` / `interface.privacyPolicyURL`
    when provided but empty, so a blank string is strictly worse than omitting
    the key. Checked here rather than per-plugin so every plugin in the catalog
    is covered, not just the ones with their own validator.
    """
    errors: list[str] = []
    for entry in catalog_data.get("plugins", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("record"), str):
            continue
        record_path = ROOT / entry["record"]
        if not record_path.exists():
            continue
        plugin_path = str(load_json(record_path).get("path", ""))
        manifest = ROOT / plugin_path / ".codex-plugin" / "plugin.json"
        if not manifest.is_file():
            continue
        interface = load_json(manifest).get("interface") or {}
        for key, value in sorted(interface.items()):
            empty = (isinstance(value, str) and not value.strip()) or (isinstance(value, list) and not value)
            if empty:
                errors.append(f"{manifest}: interface.{key} must not be empty when provided; omit the key instead")
    return errors


def command_validate(_: argparse.Namespace) -> int:
    data = catalog()
    errors = validate_catalog_shape(data)
    errors.extend(validate_platform_surfaces(data))
    errors.extend(validate_categories(data))
    errors.extend(validate_codex_interfaces(data))
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


_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def command_bump_version(args: argparse.Namespace) -> int:
    """Set a plugin's version across the surfaces that carry one, then validate.

    Keeps the catalog record, both plugin manifests, and the Claude marketplace
    entry in lockstep so a release cannot drift one of them.

    `marketplace.json` and `.agents/plugins/marketplace.json` are deliberately not
    touched: they carry no version field at all, and adding one is how drift gets
    introduced rather than avoided. See CONTRIBUTING and ADR-0001.

    Writes are staged and committed only once every target has been resolved. The
    previous order - mutate five files, then validate - left the repository
    half-bumped with no rollback whenever validation failed.
    """
    plugin_id = args.plugin_id
    version = args.version
    if not _SEMVER.match(version):
        raise SystemExit(f"not a semantic version: {version!r}")

    errors: list[str] = []
    data = catalog()
    record_rel = next((e.get("record") for e in data.get("plugins", []) if e.get("id") == plugin_id), None)
    if not isinstance(record_rel, str):
        raise SystemExit(f"plugin not found in catalog: {plugin_id}")
    record = load_json(ROOT / record_rel)
    plugin_path = str(record.get("path", ""))

    staged: list[tuple[Path, dict[str, Any]]] = []
    for path in (
        ROOT / record_rel,
        ROOT / plugin_path / ".claude-plugin" / "plugin.json",
        ROOT / plugin_path / ".codex-plugin" / "plugin.json",
    ):
        if not path.is_file():
            errors.append(f"missing version target: {path}")
            continue
        staged.append((path, {**load_json(path), "version": version}))

    mp = ROOT / ".claude-plugin" / "marketplace.json"
    if mp.is_file():
        mp_data = load_json(mp)
        if not any(entry.get("name") == plugin_id for entry in mp_data.get("plugins", [])):
            errors.append(f"{mp.name}: no entry named {plugin_id}")
        for entry in mp_data.get("plugins", []):
            if entry.get("name") == plugin_id:
                entry["version"] = version
        staged.append((mp, mp_data))

    if errors:
        # Nothing has been written yet, so there is nothing to undo.
        print("\n".join(errors), file=sys.stderr)
        return 1

    data["updated_at"] = datetime.now(UTC).strftime("%Y-%m-%dT00:00:00Z")
    staged.append((CATALOG, data))
    for path, payload in staged:
        _write_json(path, payload)

    print(f"bumped {plugin_id} to {version} across {len(staged)} versioned surface(s)")
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
