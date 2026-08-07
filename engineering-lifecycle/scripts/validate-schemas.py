#!/usr/bin/env python3
"""Validate schema files and JSON fixtures with standard-library checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eng_common import artifact_roots, plugin_root


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


def expected_type_names(schema_type: object) -> list[str]:
    if isinstance(schema_type, list):
        return [str(item) for item in schema_type]
    return [str(schema_type)]


def type_matches(value: object, schema_type: object) -> bool:
    names = expected_type_names(schema_type)
    if "null" in names and value is None:
        return True
    if "object" in names and isinstance(value, dict):
        return True
    if "array" in names and isinstance(value, list):
        return True
    if "string" in names and isinstance(value, str):
        return True
    if "integer" in names and isinstance(value, int) and not isinstance(value, bool):
        return True
    if "number" in names and isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    return "boolean" in names and isinstance(value, bool)


def validate_value(value: object, schema: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    schema_type = schema.get("type")
    if schema_type is not None and not type_matches(value, schema_type):
        expected = "|".join(expected_type_names(schema_type))
        errors.append(f"{label}: expected {expected}, got {type(value).__name__}")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{label}: value {value!r} is not one of {schema['enum']!r}")
    if isinstance(value, str) and "minLength" in schema and len(value) < int(schema["minLength"]):
        errors.append(f"{label}: string is shorter than minLength {schema['minLength']}")
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and "minimum" in schema
        and value < int(schema["minimum"])
    ):
        errors.append(f"{label}: value is below minimum {schema['minimum']}")
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{label}: missing required key {key}")
        properties = schema.get("properties", {})
        for key, prop_schema in properties.items():
            if key in value and isinstance(prop_schema, dict):
                errors.extend(validate_value(value[key], prop_schema, f"{label}.{key}"))
        if schema.get("additionalProperties") is False:
            allowed = set(properties)
            for key in value:
                if key not in allowed:
                    errors.append(f"{label}: unexpected key {key}")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        item_schema = schema["items"]
        for index, item in enumerate(value):
            errors.extend(validate_value(item, item_schema, f"{label}[{index}]"))
    return errors


def schema_key_for(path: Path) -> str | None:
    name = path.name
    parts = {part.lower() for part in path.parts}
    if name == "action-items.json":
        return "action-items"
    if name == "settings.json":
        return "tracker-settings"
    if name == "surfaced-issues.json":
        return "surfaced-issues"
    if name == "dispatch-state.json":
        return "tracker-state"
    if name == "workstreams.json":
        return "workstreams"
    if name == "handoff.json":
        return "handoff"
    if name == "human-tasks.json":
        return "human-tasks"
    if name == "hygiene-report.json":
        return "repo-hygiene"
    if name == "council-report.json":
        return "council-report"
    if name == "dashboard-data.json":
        return "dashboard-data"
    if name == "repo-profile.json":
        return "repo-profile"
    if name in {"stack.json", "tech-stack-profile.json"}:
        return "tech-stack-profile"
    if name == "lifecycle-state.json":
        return "lifecycle-state"
    if name == "missing-artifacts.json":
        return "missing-artifacts"
    if name in {"council-input.json", "input.json"} and "council" in parts:
        return "council-input"
    return None


def load_schemas(root: Path) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "schemas").glob("*.schema.json")):
        data, error = load(path)
        if error or not isinstance(data, dict):
            continue
        schemas[path.name.removesuffix(".schema.json")] = data
    return schemas


def validate_json_against_schema(path: Path, schemas: dict[str, dict[str, Any]]) -> list[str]:
    key = schema_key_for(path)
    if not key or key not in schemas:
        return []
    data, error = load(path)
    if error:
        return [f"{path}: invalid JSON: {error}"]
    return validate_value(data, schemas[key], str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Plugin root that supplies the schemas and fixtures")
    parser.add_argument(
        "--project-root",
        default=None,
        help="Also validate this repo's generated artifacts (both .project trees). Opt-in.",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else plugin_root()
    errors: list[str] = []
    schemas = load_schemas(root)
    for path in sorted((root / "schemas").glob("*.json")):
        if path.stat().st_size == 0:
            errors.append(f"{path}: empty schema")
        else:
            errors.extend(validate_schema(path))
    # Fixtures only. The plugin's own `.project` is transient runtime state that
    # any test run or stray hook can recreate in an older shape, so validating it
    # here made a green build depend on local litter rather than on the repo.
    json_roots = [root / "evals", root / "skills", root / "templates"]
    # A CONSUMING repo's generated data is validated on request. Without this the
    # plugin only ever schema-checked its own fixtures, so a real
    # dashboard-data.json or ledger that had drifted was never caught.
    if args.project_root:
        for base in artifact_roots(Path(args.project_root).resolve()):
            if base.exists():
                json_roots.append(base)
    for path in sorted({p for base in json_roots if base.exists() for p in base.rglob("*.json")}):
        if path.stat().st_size == 0:
            errors.append(f"{path}: empty JSON")
        else:
            errors.extend(validate_json(path))
            errors.extend(validate_json_against_schema(path, schemas))
    if errors:
        print("\n".join(errors))
        return 1
    print("schemas and JSON artifacts are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
