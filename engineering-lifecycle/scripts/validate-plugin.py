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
    "README.md",
    "hooks/hooks.json",
    "scripts/init-workspace.py",
    "scripts/profile-repo.py",
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


def validate_hooks(root: Path) -> list[str]:
    path = root / "hooks" / "hooks.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path}: invalid JSON: {exc}"]
    errors: list[str] = []
    for entries in data.get("hooks", {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                command = hook.get("command")
                if not command:
                    continue
                plugin_root_match = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s]+)", command)
                if plugin_root_match:
                    target = root / plugin_root_match.group(1)
                else:
                    target = root / command
                if not target.exists():
                    errors.append(f"{path}: hook command missing: {command}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else plugin_root()
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
    for path in sorted((root / "skills").glob("*/SKILL.md")):
        errors.extend(validate_skill(path))
    for path in sorted((root / "schemas").glob("*.json")):
        if path.stat().st_size == 0:
            errors.append(f"empty schema: {path.relative_to(root)}")
    for path in sorted((root / "scripts").glob("*.py")):
        if path.name != "__init__.py" and path.stat().st_size == 0:
            errors.append(f"empty script: {path.relative_to(root)}")
    errors.extend(validate_hooks(root))
    if errors:
        print("\n".join(errors))
        return 1
    print("plugin scaffold is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
