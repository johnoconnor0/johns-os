#!/usr/bin/env python3
"""Validate the Engineering Lifecycle plugin scaffold."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from eng_common import parse_front_matter, plugin_root

REQUIRED_DIRS = ["skills", "agents", "hooks", "scripts", "schemas", "references", "evals"]
REQUIRED_FILES = [
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "README.md",
    "hooks/hooks.json",
    "scripts/init-workspace.py",
    "scripts/profile-repo.py",
    # Shared modules. Everything else imports through these, so a missing one
    # breaks every hook rather than a single tool.
    "scripts/eng_common.py",
    "scripts/quality_tools.py",
    "scripts/stack_detection.py",
    "scripts/questions.py",
    "scripts/initiatives.py",
    "scripts/data_model.py",
    "scripts/references.py",
    "scripts/trackers.py",
    "scripts/tracker.py",
    "schemas/tracker-settings.schema.json",
    "schemas/surfaced-issues.schema.json",
    "scripts/validate-artifact.py",
    "scripts/validate-schemas.py",
    "scripts/validate-plugin.py",
    "scripts/sync-ledger.py",
    "scripts/council.py",
    "schemas/repo-hygiene.schema.json",
    "schemas/council-report.schema.json",
    "evals/evals.json",
    "evals/trigger-evals.json",
]


def validate_skill(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    fm, body = parse_front_matter(text)
    for key in ["name", "description"]:
        if key not in fm:
            errors.append(f"{path}: missing skill front matter key {key}")
    for section in ["Trigger", "When To Use", "Outputs", "Safety Constraints"]:
        if f"## {section}" not in body:
            errors.append(f"{path}: missing section {section}")
    return errors


def validate_codex_manifest(root: Path) -> list[str]:
    """Reject interface fields that are present but blank.

    The Codex plugin validator rejects `interface.termsOfServiceURL` and
    `interface.privacyPolicyURL` when they are provided but empty, so a blank
    string is strictly worse than omitting the key. The same applies to any
    other empty interface string or list: declaring a capability you do not
    have is a validation failure, not a placeholder.
    """
    path = root / ".codex-plugin" / "plugin.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{path}: invalid JSON: {exc}"]

    errors: list[str] = []
    interface = data.get("interface") or {}
    for key, value in sorted(interface.items()):
        if isinstance(value, str) and not value.strip():
            errors.append(f"{path}: interface.{key} must not be empty when provided; omit the key instead")
        elif isinstance(value, list) and not value:
            errors.append(f"{path}: interface.{key} must not be an empty list when provided; omit the key instead")
    for key in ("privacyPolicyURL", "termsOfServiceURL", "websiteURL"):
        value = interface.get(key)
        if isinstance(value, str) and value.strip() and not value.startswith("https://"):
            errors.append(f"{path}: interface.{key} must be an https URL")

    claude_manifest = root / ".claude-plugin" / "plugin.json"
    if claude_manifest.exists():
        try:
            claude = json.loads(claude_manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            claude = {}
        for key in ("name", "version"):
            if claude.get(key) and data.get(key) and claude[key] != data[key]:
                errors.append(f"{path}: {key} ({data[key]}) does not match .claude-plugin/plugin.json ({claude[key]})")
    return errors


def validate_hooks(root: Path) -> list[str]:
    path = root / "hooks" / "hooks.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path}: invalid JSON: {exc}"]
    errors: list[str] = []
    unsupported = sorted(set(data) - {"description", "hooks"})
    for key in unsupported:
        errors.append(f"{path}: unsupported top-level hook config field: {key}")
    for entries in data.get("hooks", {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                command = hook.get("command")
                if not command:
                    continue
                plugin_root_match = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s]+)", command)
                target = root / plugin_root_match.group(1) if plugin_root_match else root / command
                if not target.exists():
                    errors.append(f"{path}: hook command missing: {command}")
    return errors


def validate_plugin(root: Path) -> list[str]:
    """Checks that apply to any Claude plugin, not only this one.

    Split out because the scaffold requirements below (`REQUIRED_DIRS`,
    `REQUIRED_FILES`) describe *this* plugin, while everything here - skill
    sections, manifest agreement, hook targets, empty files - is true of every
    plugin in the marketplace. Keeping them together is why `ai-utilities` shipped
    four skills with none of the four required sections and nothing ever complained:
    no validator had ever been pointed at it.
    """
    errors: list[str] = []
    for path in sorted((root / "skills").glob("*/SKILL.md")):
        errors.extend(validate_skill(path))
    for path in sorted((root / "schemas").glob("*.json")):
        if path.stat().st_size == 0:
            errors.append(f"empty schema: {path.relative_to(root)}")
    for path in sorted((root / "scripts").glob("*.py")):
        if path.name != "__init__.py" and path.stat().st_size == 0:
            errors.append(f"empty script: {path.relative_to(root)}")
    errors.extend(validate_codex_manifest(root))
    if (root / "hooks" / "hooks.json").is_file():
        errors.extend(validate_hooks(root))
    return errors


def validate_scaffold(root: Path) -> list[str]:
    """The Engineering Lifecycle plugin's own required layout."""
    errors: list[str] = []
    for dirname in REQUIRED_DIRS:
        if not (root / dirname).is_dir():
            errors.append(f"missing directory: {dirname}")
    for filename in REQUIRED_FILES:
        path = root / filename
        if not path.exists():
            errors.append(f"missing file: {filename}")
        elif path.stat().st_size == 0:
            errors.append(f"empty required file: {filename}")
    return errors


def marketplace_plugins(start: Path) -> list[Path]:
    """Every plugin directory in the marketplace this plugin is installed from."""
    for candidate in [start, *start.parents]:
        found = sorted(path.parent.parent for path in candidate.glob("*/.claude-plugin/plugin.json"))
        if found:
            return found
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate every plugin in the marketplace, not only this one.",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else plugin_root()

    errors = validate_scaffold(root) + validate_plugin(root)
    checked = [root.name]
    if args.all:
        for other in marketplace_plugins(root):
            if other == root:
                continue
            checked.append(other.name)
            errors.extend(f"{other.name}: {error}" for error in validate_plugin(other))

    if errors:
        print("\n".join(errors))
        return 1
    print(f"plugin scaffold is valid ({', '.join(checked)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
