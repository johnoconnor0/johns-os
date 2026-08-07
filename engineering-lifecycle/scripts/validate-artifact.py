#!/usr/bin/env python3
"""Validate Engineering Lifecycle artifacts for basic contract compliance."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from eng_common import REQUIRED_FRONT_MATTER, artifact_roots, parse_front_matter, resolve_cli_root

REQUIRED_SECTIONS = {
    "discovery-brief": [
        "Problem",
        "Users",
        "Evidence",
        "Goals And Success Signals",
        "Assumptions",
        "Risks",
        "MVP Boundary",
        "Open Questions",
    ],
    "prd": [
        "Problem",
        "Goals",
        "Non-Goals",
        "Users",
        "User Stories",
        "Functional Requirements",
        "Non-Functional Requirements",
        "Permissions And Data Handling",
        "Assumptions",
        "Dependencies",
        "Success Metrics",
        "Acceptance Criteria",
        "Release Criteria",
        "Edge Cases",
        "Out Of Scope",
        "Open Questions",
    ],
    "ux-flow": ["Users", "Journeys", "Screens", "States", "Edge Cases", "Accessibility", "Open Questions"],
    "system-map": ["Product Context", "Components", "Data Flow", "Missing Information"],
    # Kept so plans written before the rename still validate.
    "architecture-plan": ["Decision Summary", "Alternatives Considered", "Risks"],
    "technical-design-document": [
        "Context And Scope",
        "Non-Goals",
        "Constraints",
        "Recommended Architecture",
        "Detailed Design",
        "Data Design",
        "API And Integration Design",
        "Cross-Cutting Concerns",
        "Environments",
        "Alternatives Considered",
        "Risks",
        "Migration And Rollback",
        "Open Questions",
    ],
    "entity-model": [
        "Entities",
        "Relationships",
        "Ownership",
        "Sensitivity",
        "Retention",
        "Audit And Lifecycle",
        "Migration Risk",
        "Open Questions",
    ],
    "api-contract": [
        "Purpose",
        "Consumers",
        "Endpoints Or Messages",
        "Request Shape",
        "Response Shape",
        "Errors",
        "Compatibility",
        "Open Questions",
    ],
    "implementation-plan": ["Implementation Slices", "Test Plan", "Rollback"],
    "implementation-log": ["Plan Followed", "Changes Made", "Tests Run", "Hygiene Updates", "Residual Risk"],
    "change-review": ["Findings", "Tests", "Residual Risk"],
    "test-strategy": ["Coverage", "Scenarios", "Manual QA"],
    "release-plan": [
        "Scope",
        "Preconditions",
        "Rollout",
        "Monitoring",
        "Rollback",
        "Support",
        "Post-Release Validation",
        "Open Questions",
    ],
    "repo-hygiene-report": [
        "Environment Variables",
        "Gitignore Candidates",
        "Support File Updates",
        "Risks",
        "Applied Changes",
    ],
    "council-report": [
        "Question",
        "Evidence",
        "Advisor Positions",
        "Recommendation",
        "Dissent Log",
        "Decision",
        "Confidence",
    ],
    "synthesis": [
        "Question",
        "Council Status",
        "Evidence",
        "Advisor Positions",
        "Blind Peer Review Summary",
        "Recommendation",
        "Dissent Log",
        "Decision",
        "Confidence",
    ],
}

PLACEHOLDER_RE = re.compile(
    r"\b(?:TODO|TBD|FIXME|PLACEHOLDER)\b|<[^>\n]*(?:replace|todo|placeholder|example)[^>\n]*>",
    re.IGNORECASE,
)


def validate_markdown(path: Path, root: Path | None = None) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    front_matter, body = parse_front_matter(text)
    missing = [key for key in REQUIRED_FRONT_MATTER if key not in front_matter]
    if missing:
        errors.append(f"{path}: missing front matter keys: {', '.join(missing)}")
    if not body.strip():
        errors.append(f"{path}: artifact body is empty")
    if PLACEHOLDER_RE.search(body):
        errors.append(f"{path}: unresolved placeholder")
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
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    root = resolve_cli_root(args.root).root
    paths = [Path(p) for p in args.paths]
    if not paths:
        paths = [
            item
            for base in artifact_roots(root)
            if base.exists()
            for item in list(base.rglob("*.md")) + list(base.rglob("*.json"))
        ]
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
