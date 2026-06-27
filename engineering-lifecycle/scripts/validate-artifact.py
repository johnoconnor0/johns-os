#!/usr/bin/env python3
"""Validate Engineering Lifecycle artifacts for basic contract compliance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eng_common import REQUIRED_FRONT_MATTER, parse_front_matter, repo_root


REQUIRED_SECTIONS = {
    "system-map": ["Product Context", "Components", "Data Flow", "Missing Information"],
    "architecture-plan": ["Decision Summary", "Alternatives Considered", "Risks"],
    "implementation-plan": ["Implementation Slices", "Test Plan", "Rollback"],
    "change-review": ["Findings", "Tests", "Residual Risk"],
    "test-strategy": ["Coverage", "Scenarios", "Manual QA"],
}


def validate_markdown(path: Path, root: Path | None = None) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    front_matter, body = parse_front_matter(text)
    missing = [key for key in REQUIRED_FRONT_MATTER if key not in front_matter]
    if missing:
        errors.append(f"{path}: missing front matter keys: {', '.join(missing)}")
    if not body.strip():
        errors.append(f"{path}: artifact body is empty")
    normalized = path.name.lower()
    for marker, sections in REQUIRED_SECTIONS.items():
        if marker in normalized:
            for section in sections:
                if f"## {section}" not in body and f"# {section}" not in body:
                    errors.append(f"{path}: missing section '{section}'")
    sources = front_matter.get("source_artifacts", [])
    if isinstance(sources, str):
        sources = [sources]
    for source in sources or []:
        if source in {"none", "unknown", "[]"}:
            continue
        raw_source = Path(source)
        candidates = [raw_source] if raw_source.is_absolute() else [path.parent / raw_source]
        if root and not raw_source.is_absolute():
            candidates.append(root / raw_source)
        if not any(candidate.resolve().exists() for candidate in candidates):
            errors.append(f"{path}: source artifact does not exist: {source}")
    return errors


def validate_json(path: Path) -> list[str]:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path}: invalid JSON: {exc}"]
    return []


def validate_path(path: Path, root: Path | None = None) -> list[str]:
    if not path.exists():
        return [f"{path}: does not exist"]
    if path.suffix.lower() == ".md":
        return validate_markdown(path, root)
    if path.suffix.lower() == ".json":
        return validate_json(path)
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Artifacts to validate")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = repo_root(Path(args.root))
    paths = [Path(p) for p in args.paths]
    if not paths:
        paths = list((root / ".project" / ".engineering").rglob("*.md")) + list(
            (root / ".project" / ".engineering").rglob("*.json")
        )
    errors: list[str] = []
    for path in paths:
        errors.extend(validate_path(path if path.is_absolute() else root / path, root))
    if errors:
        print("\n".join(errors))
        return 1
    print(f"validated {len(paths)} artifact(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
