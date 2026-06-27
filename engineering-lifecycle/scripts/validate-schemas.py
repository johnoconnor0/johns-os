#!/usr/bin/env python3
"""Validate schema files and JSON fixtures with standard-library checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eng_common import plugin_root


def load(path: Path) -> tuple[object | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def validate_schema(path: Path) -> list[str]:
    data, error = load(path)
    if error:
        return [f"{path}: invalid JSON: {error}"]
    errors: list[str] = []
    if not isinstance(data, dict):
        errors.append(f"{path}: schema must be an object")
    else:
        for key in ["$schema", "type"]:
            if key not in data:
                errors.append(f"{path}: missing {key}")
    return errors


def validate_json(path: Path) -> list[str]:
    _, error = load(path)
    return [f"{path}: invalid JSON: {error}"] if error else []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else plugin_root()
    errors: list[str] = []
    for path in sorted((root / "schemas").glob("*.json")):
        if path.stat().st_size == 0:
            errors.append(f"{path}: empty schema")
        else:
            errors.extend(validate_schema(path))
    for path in sorted((root / "evals").rglob("*.json")):
        if path.stat().st_size == 0:
            errors.append(f"{path}: empty JSON")
        else:
            errors.extend(validate_json(path))
    for path in sorted((root / "skills").rglob("*.json")):
        if path.stat().st_size == 0:
            errors.append(f"{path}: empty JSON")
        else:
            errors.extend(validate_json(path))
    if errors:
        print("\n".join(errors))
        return 1
    print("schemas and JSON fixtures are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
