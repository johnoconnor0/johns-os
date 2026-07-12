#!/usr/bin/env python3
"""Static validator for Claude Code skill/plugin packages.

This is intentionally conservative and dependency-free. It catches common
structure and frontmatter mistakes but does not replace `claude plugin validate`.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

Kebab = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
Semver = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def split_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---\n"):
        return None, text, "missing YAML frontmatter"
    end = text.find("\n---", 4)
    if end == -1:
        return None, text, "unterminated YAML frontmatter"
    raw = text[4:end].strip()
    body = text[end+4:]
    data = {}
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            return None, text, f"cannot parse frontmatter line: {line!r}"
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        data[key] = val
    return data, body, None


def check_skill_dir(path: Path, root: Path):
    errors = []
    warnings = []
    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"{path}: missing SKILL.md")
        return errors, warnings
    fm, body, err = split_frontmatter(skill_md)
    if err:
        errors.append(f"{skill_md}: {err}")
        return errors, warnings
    name = fm.get("name")
    desc = fm.get("description")
    if not name:
        errors.append(f"{skill_md}: missing frontmatter name")
    elif not Kebab.match(name):
        errors.append(f"{skill_md}: name is not kebab-case: {name}")
    elif path.name != name:
        warnings.append(f"{skill_md}: directory name {path.name!r} differs from frontmatter name {name!r}")
    if not desc:
        errors.append(f"{skill_md}: missing description")
    elif len(desc) < 40:
        warnings.append(f"{skill_md}: description may be too short to route reliably")
    lines = skill_md.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) > 500:
        warnings.append(f"{skill_md}: {len(lines)} lines; consider moving details to references")
    if "TODO" in body or "<replace" in body.lower():
        warnings.append(f"{skill_md}: body contains placeholder text")
    if fm.get("argument-hint") and "$ARGUMENTS" not in body:
        warnings.append(f"{skill_md}: argument-hint exists but $ARGUMENTS is not used in body")
    return errors, warnings


def check_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def check_plugin(path: Path):
    errors = []
    warnings = []
    manifest_path = path / ".claude-plugin" / "plugin.json"
    if not manifest_path.exists():
        errors.append(f"{path}: missing .claude-plugin/plugin.json")
        return errors, warnings
    manifest, err = check_json(manifest_path)
    if err:
        errors.append(f"{manifest_path}: invalid JSON: {err}")
        return errors, warnings
    name = manifest.get("name")
    version = manifest.get("version")
    if not name or not Kebab.match(str(name)):
        errors.append(f"{manifest_path}: plugin name must be kebab-case")
    if version and not Semver.match(str(version)):
        errors.append(f"{manifest_path}: version is not semantic versioning: {version}")
    for key in ["skills", "agents", "hooks", "commands", "mcpServers", "lspServers"]:
        value = manifest.get(key)
        if isinstance(value, str):
            target = (path / value).resolve()
            if not target.exists():
                warnings.append(f"{manifest_path}: {key} path does not exist: {value}")
    return errors, warnings


def main(argv):
    if len(argv) != 2:
        print("usage: check_claude_extension.py <path>", file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    if not root.exists():
        print(f"ERROR: path does not exist: {root}", file=sys.stderr)
        return 2

    errors = []
    warnings = []
    if (root / ".claude-plugin" / "plugin.json").exists():
        e, w = check_plugin(root)
        errors += e
        warnings += w
        skill_dirs = [p.parent for p in root.rglob("SKILL.md")]
    elif (root / "SKILL.md").exists():
        skill_dirs = [root]
    else:
        skill_dirs = [p.parent for p in root.rglob("SKILL.md")]
        if not skill_dirs:
            errors.append(f"{root}: no SKILL.md files found and no plugin manifest found")

    for sd in skill_dirs:
        e, w = check_skill_dir(sd, root)
        errors += e
        warnings += w

    for json_path in list(root.rglob("*.json")):
        _, err = check_json(json_path)
        if err:
            errors.append(f"{json_path}: invalid JSON: {err}")

    for bad in [".git", "node_modules", "__pycache__"]:
        if any(p.name == bad for p in root.rglob(bad)):
            warnings.append(f"{root}: package contains {bad}")

    print(f"Checked: {root}")
    print(f"Skills found: {len(skill_dirs)}")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"- {w}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"- {e}")
        return 1
    print("\nPASS: no static validation errors")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
