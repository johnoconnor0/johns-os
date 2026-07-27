#!/usr/bin/env python3
"""Keep the npx installer's version in step with the marketplace it installs.

The CLI advertises a marketplace. If its own version drifts from
`.claude-plugin/marketplace.json`, users install a version that does not match
what the package claims, and the mismatch only surfaces after installation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def main() -> int:
    cli = load(ROOT / "cli" / "package.json")
    marketplace = load(ROOT / ".claude-plugin" / "marketplace.json")

    errors: list[str] = []
    if cli.get("version") != marketplace.get("version"):
        errors.append(
            f"cli/package.json version ({cli.get('version')}) does not match "
            f".claude-plugin/marketplace.json version ({marketplace.get('version')})"
        )

    # Every plugin the CLI can install must exist in the marketplace.
    declared = {entry.get("name") for entry in marketplace.get("plugins", []) if isinstance(entry, dict)}
    cli_source = (ROOT / "cli" / "index.js").read_text(encoding="utf-8")
    for name in ("engineering-lifecycle", "business-development", "ai-utilities"):
        if name in cli_source and name not in declared:
            errors.append(f"cli/index.js references {name}, which the marketplace does not declare")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"cli and marketplace agree at version {cli.get('version')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
