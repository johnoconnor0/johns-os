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

from findings import DISMISSED_STATUSES

_OUTCOME_LABEL = {
    "passed": "PASSED",
    "failed": "FAILED",
    "not-applicable": "NOT APPLICABLE",
    "not-checked": "NOT CHECKED",
    "errored": "ERRORED",
}

_SEVERITY_ORDER = ("critical", "warning", "suggestion")

# Kept in step with findings.DISMISSED_STATUSES. Imported rather than copied, so a
# status added there cannot silently keep counting as live work here.
_DISMISSED_STATUSES = DISMISSED_STATUSES


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
    # `.get` rather than a subscript throughout: this file is hand-edited between the
    # audit and the render, and an item that lost its `status` key should not take the
    # whole report down with a KeyError.
    counts: dict[str, int] = {}
    for item in items:
        status = item.get("status", "not-started")
        counts[status] = counts.get(status, 0) + 1
    complete = counts.get("complete", 0)
    total = len(items) or 1

    inventory = next((f for f in document["families"] if f["id"] == "plan-inventory"), {})
    assessed = inventory.get("outcome") in {"passed", "failed"}
    coverage = plan.get("coverage") or {}
    unparsed = coverage.get("unparsed_sections") or []
    # Two different unknowns, and a percentage needs both answered. `assessed` asks
    # whether anything judged the items; `confident` asks whether the items are the
    # plan. The second was missing, so a six-item misparse of a twenty-one-item plan
    # rendered "4 of 6 complete (67%)" - a real numerator over a wrong denominator,
    # which is worse than no number because it reads as a measurement.
    confident = coverage.get("confident", True)
    if not assessed:
        lines = [
            f"**{len(items)} plan items were extracted from `{plan['path']}` "
            f"by the `{plan['parsed_by']}` extractor. None have been assessed yet.**",
            "",
            f"> Completion status is not established by this script: {inventory.get('reason', 'not assessed')}.",
            "> The counts below are the extractor's starting state, not a verdict.",
            "",
        ]
    elif not confident:
        lines = [
            f"**{complete} of {len(items)} extracted plan items are complete. "
            "No percentage is given: the extractor did not account for the whole plan.**",
            "",
            f"> Parsed from `{plan['path']}` by the `{plan['parsed_by']}` extractor, covering "
            f"{coverage.get('sections_parsed', 0)} of {coverage.get('candidate_sections', 0)} "
            "sections that look like they state work.",
            "> A percentage over an incomplete inventory would be a measurement of the wrong thing.",
            "",
        ]
    else:
        lines = [
            f"**{complete} of {len(items)} plan items complete ({round(complete / total * 100)}%).** "
            f"Parsed from `{plan['path']}` by the `{plan['parsed_by']}` extractor.",
            "",
        ]
    if unparsed:
        lines.append(
            f"> **{len(unparsed)} section(s) state work that produced no plan items** and are "
            "unaudited by this run: "
            + ", ".join(f"`{heading}`" for heading in unparsed[:8])
            + ("..." if len(unparsed) > 8 else "")
            + ". Check whether the plan is written in a form the extractor did not read."
        )
        lines.append("")
    if counts:
        lines.append("| Status | Count |")
        lines.append("| --- | ---: |")
        for status, count in sorted(counts.items()):
            lines.append(f"| {status} | {count} |")
        lines.append("")
    unverifiable = [item for item in items if item.get("status") == "unverifiable"]
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


def _is_dismissed(finding: dict[str, Any]) -> bool:
    return finding.get("status", "open") in _DISMISSED_STATUSES


def _evidence_caveats(document: dict[str, Any]) -> list[str]:
    """What this audit does not know, said once and near the top.

    Three separate `not-checked` rows in a verdict table do not add up to "there is no
    test evidence here" for anybody skimming for a verdict, and a completion audit
    that ran no tests cannot say whether the work functions. Saying it plainly is the
    difference between a reader knowing that and having to derive it.
    """
    by_id = {family["id"]: family for family in document["families"]}
    verdict = {"passed", "failed"}
    missing = [
        label
        for family_id, label in (("tests", "test"), ("static-analysis", "lint or typecheck"), ("build", "build"))
        if family_id in by_id and by_id[family_id].get("outcome") not in verdict | {"not-applicable"}
    ]
    lines: list[str] = []
    if missing:
        lines += [
            f"> **This audit contains no {', '.join(missing)} evidence.** "
            "Those families did not run - see *Not run* below for why. Nothing here "
            "establishes whether the implemented work functions.",
            "",
        ]
    for warning in document.get("scope_warnings", []) or []:
        lines += [f"> **Scope warning.** {warning}", ""]
    if document.get("validation_errors"):
        # Previously written into findings.json and never rendered, so a document that
        # failed its own validation still produced a clean-looking report.
        lines += [
            f"> **This document failed {len(document['validation_errors'])} validation check(s).** "
            "See `validation_errors` in `findings.json`.",
            "",
        ]
    return lines


def render(document: dict[str, Any]) -> str:
    findings = {item["id"]: item for item in document["findings"]}
    # Counted here rather than read from `totals`, because this document is meant to
    # be hand-edited: the model writes its assessment into findings.json and
    # re-renders, and a persisted count does not know that happened. Trusting
    # `totals` is how a header said "Critical 7" over six findings that had been
    # examined and dismissed with evidence.
    live = [item for item in document["findings"] if not _is_dismissed(item)]
    dismissed = [item for item in document["findings"] if _is_dismissed(item)]
    totals = {severity: sum(1 for item in live if item["severity"] == severity) for severity in _SEVERITY_ORDER}
    lines: list[str] = [
        "# Plan Completion Audit",
        "",
        f"- **Run:** `{document['run_id']}`",
        f"- **Generated:** {document['generated_at']}",
        f"- **Root:** `{document['root']}`",
        "",
        "---",
        "",
        *_evidence_caveats(document),
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
        owned_open = sum(1 for fid in family["finding_ids"] if fid in findings and not _is_dismissed(findings[fid]))
        lines.append(
            f"| {family['title']} | **{_OUTCOME_LABEL.get(family['outcome'], family['outcome'])}** | {owned_open} |"
        )
    lines += [
        "",
        f"Critical {totals.get('critical', 0)} · warning {totals.get('warning', 0)} · "
        f"suggestion {totals.get('suggestion', 0)}.",
        "",
    ]
    if dismissed:
        lines += [
            f"{len(dismissed)} finding(s) were examined and dismissed; they are excluded from "
            "the counts above and listed at the end with the reason.",
            "",
        ]
    lines += ["---", ""]

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
    lines += _dismissed_section(dismissed)
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
    open_owned = [finding for finding in owned if not _is_dismissed(finding)]
    if open_owned:
        lines += ["| ID | Severity | Location | Finding |", "| --- | --- | --- | --- |"]
        for finding in open_owned:
            lines.append(f"| {finding['id']} | {finding['severity']} | `{_where(finding)}` | {finding['title']} |")
        lines.append("")
    elif family["outcome"] == "passed":
        lines.append("No findings.")
        lines.append("")
    elif owned:
        # It found something and everything it found was dismissed. Saying so is the
        # point: the outcome stays `failed` because the check did fire, and an empty
        # section under a FAILED heading would read as a rendering bug.
        lines.append(f"All {len(owned)} finding(s) from this family were examined and dismissed. See below.")
        lines.append("")
    return lines


def _where(finding: dict[str, Any]) -> str:
    evidence = finding["evidence"][0] if finding["evidence"] else {}
    where = evidence.get("path", "")
    if evidence.get("line"):
        where = f"{where}:{evidence['line']}"
    return where


def _dismissed_section(dismissed: list[dict[str, Any]]) -> list[str]:
    """What was checked and set aside, with the reason it was set aside.

    Without this the assessment simply vanished: a run that examined six criticals
    and dismissed all six rendered identically to one that had examined none.
    """
    if not dismissed:
        return []
    lines = [
        f"## Dismissed ({len(dismissed)})",
        "",
        "Raised by a mechanical check, then examined and judged to need no action.",
        "Excluded from the counts and the prioritised actions above.",
        "",
        "| ID | Was | Location | Finding | Status | Why |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for finding in dismissed:
        reason = str(finding.get("status_reason") or "").replace("|", "\\|") or "_no reason recorded_"
        lines.append(
            f"| {finding['id']} | {finding['severity']} | `{_where(finding)}` | {finding['title']} "
            f"| {finding.get('status')} | {reason} |"
        )
    lines.append("")
    return lines


def _action_list(document: dict[str, Any], findings: dict[str, Any]) -> list[str]:
    lines = ["## Prioritised actions", ""]
    inventory = next((f for f in document["families"] if f["id"] == "plan-inventory"), {})
    assessed = inventory.get("outcome") in {"passed", "failed"}
    unverifiable = [item for item in document.get("plan_items", []) if item.get("status") == "unverifiable"]
    # Every item reads as not-started until something assesses it. Listing them as
    # outstanding work before that happens would be the same unearned verdict.
    not_started = (
        [item for item in document.get("plan_items", []) if item.get("status") == "not-started"] if assessed else []
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
        group = [item for item in findings.values() if item["severity"] == severity and not _is_dismissed(item)]
        if not group:
            continue
        any_findings = True
        lines.append(f"### {severity.title()} ({len(group)})")
        lines.append("")
        for finding in group:
            lines.append(f"1. `{_where(finding)}` — {finding['title']}")
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
