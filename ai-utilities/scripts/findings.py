#!/usr/bin/env python3
"""The audit's machine-readable output, and the identity model behind it.

Two skills used to talk to each other through markdown. `audit-resolver` shipped a
`parse-audit-report.sh` that described itself as "heuristic, not a strict parser" and
warned the caller to sanity-check its own output count. A structured artefact removes
the guessing from that seam entirely, and gives the tracker layer something to hash.

## Five outcomes, not three

    passed | failed | not-applicable | not-checked | errored

Without an explicit `passed`, "ran and found nothing" is indistinguishable in JSON
from "did not run", which is the exact conflation this rebuild exists to end - the
old skill's own principle section warned about it in prose and then had no way to
express it. And "the command crashed" is not "the command found problems".

`not-applicable`, `not-checked` and `errored` each REQUIRE a reason. That is checked
here rather than asked for in documentation, because the previous version asked in
documentation.

## Two hashes, doing two different jobs

`linear-sync.py` hashes a task over `(title, status, owner, priority, description)`
and that works, because a ledger task already has a stable id. A finding has none,
and its description embeds `file:line` - so hashing the obvious fields gives an
identity that changes every time somebody adds an import above the finding, and the
tracker creates a second issue for the same problem.

    identity      decides create-vs-match. Line number deliberately excluded.
    content_hash  decides update-vs-skip. Includes the line, so a finding that
                  moved updates its issue instead of being re-created.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "plan-completion-audit/findings@1"

OUTCOMES = ("passed", "failed", "not-applicable", "not-checked", "errored")
# The three that are not a verdict about the code. Each has to say why, or the
# report cannot distinguish "this repo has no frontend" from "the tool was missing".
OUTCOMES_NEEDING_REASON = ("not-applicable", "not-checked", "errored")

SEVERITIES = ("critical", "warning", "suggestion")

# What the model concluded about a finding a mechanical check raised. `Finding.status`
# was a free string that nothing validated and the renderer never read, so a run that
# examined six criticals and dismissed all six rendered identically to one that had
# examined none of them: still six criticals in the header, no trace of the work. The
# family vocabulary above was already the right design; this is that design applied
# one level down.
FINDING_STATUSES = ("open", "false-positive", "accepted-risk", "fixed")
# Anything other than `open` is a claim that this finding needs no action, which is
# exactly the claim that has to carry its evidence.
FINDING_STATUSES_NEEDING_REASON = ("false-positive", "accepted-risk", "fixed")
# The statuses that take a finding out of the live counts.
DISMISSED_STATUSES = ("false-positive", "accepted-risk", "fixed")

_DIGITS = re.compile(r"\d+")


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


@dataclass
class Evidence:
    path: str = ""
    line: int | None = None
    excerpt: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "line": self.line, "excerpt": self.excerpt}


@dataclass
class Finding:
    family: str
    rule: str
    severity: str
    title: str
    detail: str = ""
    evidence: list[Evidence] = field(default_factory=list)
    plan_items: list[str] = field(default_factory=list)
    route: dict[str, Any] = field(default_factory=dict)
    suggested_strategy: str = "plan-first"
    status: str = "open"
    status_reason: str = ""
    id: str = ""

    @property
    def primary_path(self) -> str:
        return self.evidence[0].path if self.evidence else ""

    @property
    def dismissed(self) -> bool:
        return self.status in DISMISSED_STATUSES

    def validate(self) -> list[str]:
        errors: list[str] = []
        label = self.id or self.rule
        if self.severity not in SEVERITIES:
            errors.append(f"{label}: unknown severity {self.severity!r}")
        if self.status not in FINDING_STATUSES:
            errors.append(f"{label}: unknown status {self.status!r}")
        if self.status in FINDING_STATUSES_NEEDING_REASON and not self.status_reason.strip():
            errors.append(f"{label}: status {self.status!r} must state a reason")
        return errors

    @property
    def identity(self) -> str:
        """Stable across a line move, because a moved finding is the same finding."""
        return _digest(self.family, self.primary_path, self.rule, _DIGITS.sub("#", self.title))

    @property
    def content_hash(self) -> str:
        """Changes when anything worth pushing to the tracker changed, line included."""
        payload = json.dumps(
            {
                "title": self.title,
                "severity": self.severity,
                "status": self.status,
                "status_reason": self.status_reason,
                "evidence": [item.as_dict() for item in self.evidence],
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "identity": self.identity,
            "content_hash": self.content_hash,
            "family": self.family,
            "rule": self.rule,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "evidence": [item.as_dict() for item in self.evidence],
            "plan_items": self.plan_items,
            "route": self.route,
            "suggested_strategy": self.suggested_strategy,
            "status": self.status,
            "status_reason": self.status_reason,
            "tracker": {"provider": None, "issue_id": None, "url": None},
        }


@dataclass
class FamilyResult:
    id: str
    title: str
    outcome: str
    reason: str = ""
    applies_because: str = ""
    commands: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.outcome not in OUTCOMES:
            errors.append(f"{self.id}: unknown outcome {self.outcome!r}")
        if self.outcome in OUTCOMES_NEEDING_REASON and not self.reason.strip():
            errors.append(f"{self.id}: outcome {self.outcome!r} must state a reason")
        if self.outcome == "failed" and not self.findings:
            errors.append(f"{self.id}: outcome 'failed' with no findings")
        if self.outcome == "passed" and self.findings:
            errors.append(f"{self.id}: outcome 'passed' with {len(self.findings)} finding(s)")
        return errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "outcome": self.outcome,
            "reason": self.reason,
            "applies_because": self.applies_because,
            "commands": self.commands,
            "finding_ids": [finding.id for finding in self.findings],
        }


def assign_ids(results: list[FamilyResult]) -> list[Finding]:
    """`F001`, `F002`, ... in a stable order, and the flat list they name."""
    flat: list[Finding] = []
    for result in results:
        for finding in result.findings:
            flat.append(finding)
    order = {name: index for index, name in enumerate(SEVERITIES)}
    flat.sort(key=lambda item: (order.get(item.severity, 99), item.family, item.primary_path, item.title))
    for index, finding in enumerate(flat, start=1):
        finding.id = f"F{index:03d}"
    return flat


def build_document(
    *,
    run_id: str,
    generated_at: str,
    root: str,
    plan: dict[str, Any],
    stack: dict[str, Any],
    results: list[FamilyResult],
    plan_items: list[dict[str, Any]],
) -> dict[str, Any]:
    findings = assign_ids(results)
    # Severity counts are over OPEN findings only. A dismissed finding that still
    # counts is how "Critical 7" survived six documented dismissals and told the
    # reader there were seven things to fix.
    live = [item for item in findings if not item.dismissed]
    counts = {severity: sum(1 for item in live if item.severity == severity) for severity in SEVERITIES}
    dismissed = {
        status: sum(1 for item in findings if item.status == status)
        for status in DISMISSED_STATUSES
        if any(item.status == status for item in findings)
    }
    by_outcome = {outcome: sum(1 for item in results if item.outcome == outcome) for outcome in OUTCOMES}
    return {
        "schema": SCHEMA,
        "run_id": run_id,
        "generated_at": generated_at,
        "root": root,
        "plan": plan,
        "stack": stack,
        "families": [result.as_dict() for result in results],
        "findings": [finding.as_dict() for finding in findings],
        "plan_items": plan_items,
        "totals": {
            **counts,
            **{f"families_{outcome.replace('-', '_')}": count for outcome, count in by_outcome.items()},
            "findings_open": len(live),
            "findings_dismissed": len(findings) - len(live),
            "dismissed_by_status": dismissed,
            "plan_items": len(plan_items),
            "plan_items_complete": sum(1 for item in plan_items if item.get("status") == "complete"),
        },
    }


def validate_document(document: dict[str, Any], registered: list[str]) -> list[str]:
    """Structural checks the audit must pass before its report is written.

    The `registered` cross-check is the replacement for the old skill's "Never skip a
    phase" instruction. Prose the model can route around becomes a condition the run
    fails on - which is exactly what happened to the prose version, in the one real
    run on record.
    """
    errors: list[str] = []
    if document.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")
    seen = {family["id"] for family in document.get("families", [])}
    missing = [name for name in registered if name not in seen]
    if missing:
        errors.append("families registered but absent from the report: " + ", ".join(sorted(missing)))
    for family in document.get("families", []):
        if family.get("outcome") not in OUTCOMES:
            errors.append(f"{family.get('id')}: unknown outcome {family.get('outcome')!r}")
        if family.get("outcome") in OUTCOMES_NEEDING_REASON and not str(family.get("reason", "")).strip():
            errors.append(f"{family.get('id')}: outcome {family.get('outcome')!r} must state a reason")
    known = {finding["id"] for finding in document.get("findings", [])}
    for family in document.get("families", []):
        for finding_id in family.get("finding_ids", []):
            if finding_id not in known:
                errors.append(f"{family.get('id')}: names unknown finding {finding_id}")
    # Findings were never validated at all. `severity` outside SEVERITIES sorts last
    # via a `99` fallback and drops out of the counts silently, and `status` had no
    # vocabulary to be outside of. Both are checked here because this is the only
    # validator the audit actually calls, and because this document gets hand-edited:
    # the model writes its assessment straight into findings.json, so the vocabulary
    # is worth nothing unless something rejects a typo in it.
    for finding in document.get("findings", []):
        label = finding.get("id") or finding.get("rule")
        if finding.get("severity") not in SEVERITIES:
            errors.append(f"{label}: unknown severity {finding.get('severity')!r}")
        status = finding.get("status", "open")
        if status not in FINDING_STATUSES:
            errors.append(f"{label}: unknown status {status!r}")
        if status in FINDING_STATUSES_NEEDING_REASON and not str(finding.get("status_reason", "")).strip():
            errors.append(f"{label}: status {status!r} must state a reason")
    return errors
