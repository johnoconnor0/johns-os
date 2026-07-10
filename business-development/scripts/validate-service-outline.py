#!/usr/bin/env python3
"""Validate a generated Service Outline: front matter + required modules.

Deterministic check the service-outline skill runs at the end of its workflow.
Confirms the required front matter is present, every core module heading exists,
and any addenda declared in `included_addenda` are actually present. Unresolved
`[TBC]` placeholders are reported as warnings, not failures.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REQUIRED_FRONT_MATTER = ["service_name", "service_type", "skill", "status", "created_at"]

CORE_MODULES = [
    "Service Overview",
    "Customer Fit and Qualification",
    "Scope and Deliverables",
    "Delivery Plan",
    "Roles, Responsibilities, and Client Inputs",
    "Success Measurement and Reporting",
    "Risks, Dependencies, and Constraints",
    "Support, Warranty, and Handover",
]

ADDENDA = {
    "technical-security-compliance": "Technical, Security, and Compliance Addendum",
    "ai-service": "AI Service Addendum",
}


def split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip("\n")
    body = text[end + 4 :]
    fm: dict = {}
    for line in raw.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            fm[key] = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
        else:
            fm[key] = value.strip('"').strip("'")
    return fm, body


def heading_text(body: str) -> str:
    return "\n".join(ln.strip() for ln in body.splitlines() if ln.lstrip().startswith("#")).lower()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Path to the generated service outline markdown")
    args = parser.parse_args()
    path = Path(args.path)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    fm, body = split_front_matter(path.read_text(encoding="utf-8", errors="ignore"))
    headings = heading_text(body)
    errors: list[str] = []

    for key in REQUIRED_FRONT_MATTER:
        if not fm.get(key):
            errors.append(f"missing front matter key: {key}")

    for title in CORE_MODULES:
        if title.lower() not in headings:
            errors.append(f"missing required module: {title}")

    included = fm.get("included_addenda") or []
    if isinstance(included, str):
        included = [included]
    for key, title in ADDENDA.items():
        if key in included and title.lower() not in headings:
            errors.append(f"included_addenda lists '{key}' but the '{title}' section is missing")

    tbc = body.count("[TBC]")
    if tbc:
        print(f"warning: {tbc} unresolved [TBC] placeholder(s) remain")

    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1
    print(f"service outline is valid: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
