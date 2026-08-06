#!/usr/bin/env python3
"""Find an audit's findings and hand them to the resolver as one shape.

`audit-resolver` used to read the markdown report through `parse-audit-report.sh`,
a script whose own header called it "heuristic, not a strict parser" and told the
caller to sanity-check its output count by hand. Two skills negotiating through
prose is a seam that cannot be made reliable, and it does not need to be: the audit
now emits `findings.json`.

Older reports still exist on disk, so markdown remains readable - but through a
converter that produces the same document shape, stamped `source:
"markdown-fallback"` so a degraded input is visible rather than assumed. One input
shape downstream, always.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from audit_common import AUDIT_DIR, read_json, relpath, repo_root

SEVERITIES = ("critical", "warning", "suggestion")

# `path/to/file.ext:42`, or without the line.
_LOCATION = re.compile(r"`([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+)(?::(\d+))?`")
_SEVERITY = re.compile(r"\b(CRITICAL|WARNING|SUGGESTION)\b", re.IGNORECASE)
_TABLE_ROW = re.compile(r"^\s*\|")


def discover(root: Path) -> Path | None:
    """The newest audit run's findings, whichever shape it was written in.

    Scoped to the audit folder on purpose. A previous version globbed
    `**/*audit*.md` across the tree, which also matched the resolver's own ledgers
    and picked the wrong file. Run directories and legacy bare reports both carry a
    `YYYY-MM-DD_HHMMSS` name, so sorting by name is chronological for both.
    """
    base = root / AUDIT_DIR
    if not base.is_dir():
        return None
    candidates: list[tuple[str, Path]] = []
    for entry in base.iterdir():
        if entry.is_dir() and (entry / "findings.json").is_file():
            candidates.append((entry.name, entry / "findings.json"))
        elif entry.is_file() and entry.suffix == ".md":
            candidates.append((entry.stem, entry))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def load(path: Path) -> dict[str, Any]:
    """A findings document from either shape, with its provenance recorded."""
    if path.suffix == ".json":
        document = read_json(path, None)
        if not isinstance(document, dict):
            raise SystemExit(f"{path} is not a readable findings document")
        document.setdefault("source", "findings.json")
        return document
    document = from_markdown(path)
    return document


def from_markdown(path: Path) -> dict[str, Any]:
    """Best-effort findings from a pre-structured markdown report.

    Deliberately conservative. It reports how many rows it could not interpret,
    because a parser that silently drops findings is how a resolver comes to close
    an audit it never fully read.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    findings: list[dict[str, Any]] = []
    unparsed = 0
    for line in text.splitlines():
        if not _TABLE_ROW.match(line) and not line.lstrip().startswith(("-", "*")):
            continue
        severity_match = _SEVERITY.search(line)
        if not severity_match:
            continue
        location = _LOCATION.search(line)
        if not location:
            unparsed += 1
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        title = next((cell for cell in reversed(cells) if len(cell) > 12 and "`" not in cell), line.strip()[:160])
        findings.append(
            {
                "id": f"F{len(findings) + 1:03d}",
                "identity": "",
                "content_hash": "",
                "family": "legacy",
                "rule": "legacy/markdown",
                "severity": severity_match.group(1).lower(),
                "title": title,
                "detail": "",
                "evidence": [
                    {
                        "path": location.group(1),
                        "line": int(location.group(2)) if location.group(2) else None,
                        "excerpt": "",
                    }
                ],
                "plan_items": [],
                "route": {"kind": "agent", "target": "", "available": None},
                "suggested_strategy": "plan-first",
                "status": "open",
                "tracker": {"provider": None, "issue_id": None, "url": None},
            }
        )
    return {
        "schema": "plan-completion-audit/findings@1",
        "source": "markdown-fallback",
        "source_path": path.as_posix(),
        "run_id": path.stem,
        "generated_at": "",
        "root": "",
        "plan": {"path": None, "parsed_by": None, "item_count": 0},
        "stack": {},
        "families": [
            {
                "id": "legacy",
                "title": "Legacy markdown report",
                "outcome": "not-checked",
                "reason": (
                    f"converted from a pre-structured markdown report; {unparsed} row(s) named a severity "
                    "but no location and could not be converted"
                ),
                "applies_because": "",
                "commands": [],
                "finding_ids": [item["id"] for item in findings],
            }
        ],
        "findings": findings,
        "plan_items": [],
        "totals": {
            severity: sum(1 for item in findings if item["severity"] == severity) for severity in SEVERITIES
        },
        "unconverted_rows": unparsed,
    }


def select(
    document: dict[str, Any],
    severities: tuple[str, ...] = SEVERITIES,
    families: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    chosen = [item for item in document.get("findings", []) if item["severity"] in severities]
    if families:
        chosen = [item for item in chosen if item["family"] in families]
    order = {name: index for index, name in enumerate(SEVERITIES)}
    return sorted(chosen, key=lambda item: (order.get(item["severity"], 99), item["family"], item["id"]))


def summarise(document: dict[str, Any]) -> dict[str, Any]:
    findings = document.get("findings", [])
    families = document.get("families", [])
    by_family: dict[str, int] = {}
    for item in findings:
        by_family[item["family"]] = by_family.get(item["family"], 0) + 1
    return {
        "source": document.get("source", "findings.json"),
        "run_id": document.get("run_id"),
        "total": len(findings),
        "by_severity": {sev: sum(1 for item in findings if item["severity"] == sev) for sev in SEVERITIES},
        "by_family": by_family,
        # Surfaced because a resolver that closes every finding while three families
        # never ran has not finished the audit, it has finished part of one.
        "families_not_run": [
            {"id": family["id"], "outcome": family["outcome"], "reason": family["reason"]}
            for family in families
            if family["outcome"] in {"not-applicable", "not-checked", "errored"}
        ],
        "plan_items_unverifiable": [
            item["id"] for item in document.get("plan_items", []) if item.get("status") == "unverifiable"
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", default="", help="Path to findings.json or a legacy markdown report")
    parser.add_argument("--severity", default="", help="Comma-separated subset of critical,warning,suggestion")
    parser.add_argument("--family", default="", help="Comma-separated family ids")
    parser.add_argument("--summary", action="store_true", help="Print the summary rather than the findings")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root not in ("", ".") else repo_root(Path("."))
    path = Path(args.report) if args.report else discover(root)
    if path is None:
        raise SystemExit(
            "No audit found under .project/audits/plan-completion-audit/. "
            "Run /ai-utilities:plan-completion-audit first."
        )
    if not path.is_absolute():
        path = root / path
    document = load(path)

    if args.summary:
        print(json.dumps({**summarise(document), "path": relpath(path, root)}, indent=2, sort_keys=True))
        return 0
    severities = tuple(item.strip() for item in args.severity.split(",") if item.strip()) or SEVERITIES
    families = tuple(item.strip() for item in args.family.split(",") if item.strip())
    print(json.dumps(select(document, severities, families), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
