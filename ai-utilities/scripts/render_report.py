#!/usr/bin/env python3
"""Turn findings.json into the human-readable report.

A fold over what actually ran, not a form to fill in. The template this replaces was
a fixed eleven-section document with Supabase schema tables and a frontend-backend
alignment matrix, so a Python repository with no database got nine sections of
ceremony and two honest N/A rows.

Families that did not apply are collapsed into one line each at the end, with their
reason, so the report says what it did not look at without spending a section on it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_OUTCOME_LABEL = {
    "passed": "PASSED",
    "failed": "FAILED",
    "not-applicable": "NOT APPLICABLE",
    "not-checked": "NOT CHECKED",
    "errored": "ERRORED",
}

_SEVERITY_ORDER = ("critical", "warning", "suggestion")


def _plan_summary(document: dict[str, Any]) -> list[str]:
    plan = document["plan"]
    items = document.get("plan_items", [])
    if plan.get("parsed_by") is None:
        return [
            "> **No plan was parsed.** Nothing in this report has been measured against an",
            "> inventory of intended work. Treat the findings as a code review, not as a",
            "> completion audit, and re-run with an explicit plan path.",
            "",
        ]
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    complete = counts.get("complete", 0)
    total = len(items) or 1

    inventory = next((f for f in document["families"] if f["id"] == "plan-inventory"), {})
    assessed = inventory.get("outcome") in {"passed", "failed"}
    if not assessed:
        # Printing "0 of 19 complete (0%)" when nothing assessed completion is the
        # precise failure this rebuild exists to end - a number that reads as a
        # measurement and is actually an absence of one.
        lines = [
            f"**{len(items)} plan items were extracted from `{plan['path']}` "
            f"by the `{plan['parsed_by']}` extractor. None have been assessed yet.**",
            "",
            f"> Completion status is not established by this script: {inventory.get('reason', 'not assessed')}.",
            "> The counts below are the extractor's starting state, not a verdict.",
            "",
        ]
    else:
        lines = [
            f"**{complete} of {len(items)} plan items complete ({round(complete / total * 100)}%).** "
            f"Parsed from `{plan['path']}` by the `{plan['parsed_by']}` extractor.",
            "",
        ]
    if counts:
        lines.append("| Status | Count |")
        lines.append("| --- | ---: |")
        for status, count in sorted(counts.items()):
            lines.append(f"| {status} | {count} |")
        lines.append("")
    unverifiable = [item for item in items if item["status"] == "unverifiable"]
    if unverifiable:
        lines.append(
            "Items marked **unverifiable** name a file, script or command that does not "
            "resolve. They have not been shown complete and have not been shown incomplete."
        )
        lines.append("")
        for item in unverifiable:
            lines.append(f"- `{item['id']}` {item['title']} — {item['reason']}")
        lines.append("")
    return lines


def _stack_summary(stack: dict[str, Any]) -> list[str]:
    def listed(key: str) -> str:
        return ", ".join(stack.get(key) or []) or "none detected"

    return [
        "| Detected | Value |",
        "| --- | --- |",
        f"| Frameworks | {listed('frameworks')} |",
        f"| Backend | {listed('backend')} |",
        f"| Database | {listed('database')} |",
        f"| Package manager | {stack.get('package_manager') or 'none detected'} |",
        f"| Detector | `{stack.get('detector')}` |",
        "",
        "Check families are gated on this. A family that does not apply says so with a",
        "reason rather than reporting a pass it did not earn.",
        "",
    ]


def render(document: dict[str, Any]) -> str:
    findings = {item["id"]: item for item in document["findings"]}
    totals = document["totals"]
    lines: list[str] = [
        "# Plan Completion Audit",
        "",
        f"- **Run:** `{document['run_id']}`",
        f"- **Generated:** {document['generated_at']}",
        f"- **Root:** `{document['root']}`",
        "",
        "---",
        "",
        "## Completion",
        "",
        *_plan_summary(document),
        "## Stack",
        "",
        *_stack_summary(document["stack"]),
        "## Verdicts",
        "",
        "| Family | Outcome | Findings |",
        "| --- | --- | ---: |",
    ]
    for family in document["families"]:
        lines.append(
            f"| {family['title']} | **{_OUTCOME_LABEL.get(family['outcome'], family['outcome'])}** "
            f"| {len(family['finding_ids'])} |"
        )
    lines += [
        "",
        f"Critical {totals.get('critical', 0)} · warning {totals.get('warning', 0)} · "
        f"suggestion {totals.get('suggestion', 0)}.",
        "",
        "---",
        "",
    ]

    ran = [family for family in document["families"] if family["outcome"] in {"passed", "failed", "errored"}]
    for family in ran:
        lines += _family_section(family, findings)

    skipped = [family for family in document["families"] if family["outcome"] in {"not-applicable", "not-checked"}]
    if skipped:
        lines += [f"## Not run ({len(skipped)})", "", "Each with the reason it was not run.", ""]
        for family in skipped:
            label = _OUTCOME_LABEL[family["outcome"]]
            lines.append(f"- **{family['title']}** — {label.lower()}: {family['reason']}")
        lines.append("")

    lines += _action_list(document, findings)
    lines += [
        "---",
        "",
        "Machine-readable findings for this run are in `findings.json` beside this file.",
        "To action them, run `/ai-utilities:audit-resolve`.",
        "",
    ]
    return "\n".join(lines)


def _family_section(family: dict[str, Any], findings: dict[str, Any]) -> list[str]:
    lines = [f"## {family['title']} — {_OUTCOME_LABEL.get(family['outcome'], family['outcome'])}", ""]
    if family.get("applies_because"):
        lines.append(f"*Ran because: {family['applies_because']}.*")
        lines.append("")
    if family.get("reason"):
        lines.append(f"*{family['reason']}*")
        lines.append("")
    for command in family.get("commands", []):
        if command.get("cmd"):
            lines.append(f"- `{command['cmd']}` — exit {command.get('exit')}")
    if family.get("commands"):
        lines.append("")
    owned = [findings[fid] for fid in family["finding_ids"] if fid in findings]
    if owned:
        lines += ["| ID | Severity | Location | Finding |", "| --- | --- | --- | --- |"]
        for finding in owned:
            evidence = finding["evidence"][0] if finding["evidence"] else {}
            where = evidence.get("path", "")
            if evidence.get("line"):
                where = f"{where}:{evidence['line']}"
            lines.append(f"| {finding['id']} | {finding['severity']} | `{where}` | {finding['title']} |")
        lines.append("")
    elif family["outcome"] == "passed":
        lines.append("No findings.")
        lines.append("")
    return lines


def _action_list(document: dict[str, Any], findings: dict[str, Any]) -> list[str]:
    lines = ["## Prioritised actions", ""]
    inventory = next((f for f in document["families"] if f["id"] == "plan-inventory"), {})
    assessed = inventory.get("outcome") in {"passed", "failed"}
    unverifiable = [item for item in document.get("plan_items", []) if item["status"] == "unverifiable"]
    # Every item reads as not-started until something assesses it. Listing them as
    # outstanding work before that happens would be the same unearned verdict.
    not_started = (
        [item for item in document.get("plan_items", []) if item["status"] == "not-started"] if assessed else []
    )
    if not_started:
        lines.append(f"**{len(not_started)} plan item(s) with no implementation found.** These come first.")
        lines.append("")
        for item in not_started:
            lines.append(f"1. `{item['id']}` {item['title']} — {item['source']}")
        lines.append("")
    if unverifiable:
        lines.append(f"**{len(unverifiable)} plan item(s) could not be verified either way.**")
        lines.append("")
    any_findings = False
    for severity in _SEVERITY_ORDER:
        group = [item for item in findings.values() if item["severity"] == severity]
        if not group:
            continue
        any_findings = True
        lines.append(f"### {severity.title()} ({len(group)})")
        lines.append("")
        for finding in group:
            evidence = finding["evidence"][0] if finding["evidence"] else {}
            where = evidence.get("path", "")
            if evidence.get("line"):
                where = f"{where}:{evidence['line']}"
            lines.append(f"1. `{where}` — {finding['title']}")
        lines.append("")
    if not any_findings and not not_started and not unverifiable:
        lines.append("Nothing outstanding from the families that ran.")
        lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("findings", help="Path to a findings.json")
    parser.add_argument("--out", default="", help="Write here instead of stdout")
    args = parser.parse_args()
    document = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    text = render(document)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
