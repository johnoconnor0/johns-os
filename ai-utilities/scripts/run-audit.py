#!/usr/bin/env python3
"""Run the deterministic half of a plan-completion audit.

What this script establishes, the model does not have to assert: which families are
relevant here, which of those could run, what each one found, and which plan items
name something that does not exist. What it cannot establish - whether a plan item is
genuinely implemented, whether a deviation was reasonable - is left to the skill,
with the inventory and the evidence already assembled.

Writes two artefacts into one directory per run:

    .project/audits/plan-completion-audit/<TIMESTAMP>/findings.json
    .project/audits/plan-completion-audit/<TIMESTAMP>/report.md

A directory rather than the old bare `<TIMESTAMP>.md`, because there are now two
artefacts. The names still sort chronologically, so `audit-resolver`'s
newest-by-name discovery is unaffected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from audit_common import audit_dir, now_iso, relpath, repo_root, run_id, write_json, write_text
from checks import (
    collect_files,
    run_command_family,
    run_dead_code,
    run_dependency_audit,
    run_repo_hygiene,
    run_secrets,
    run_unfinished_markers,
)
from families import REGISTRY, Ctx, registered_ids
from findings import FamilyResult, build_document, validate_document
from plan_parse import find_plan, mark_unverifiable, parse_plan
from stack_probe import resolve_stack

# Families whose finding-production is the model's job, not a command's. They still
# appear in the report with an explicit outcome; they simply carry no findings from
# this script. Being listed here is what stops them looking like a silent pass.
_MODEL_DRIVEN = {
    "plan-inventory": "the implementation status of each plan item is assessed by the skill, not by a command",
    "interface-alignment": "cross-side alignment is assessed by the skill against both sides",
    "data-layer": "schema review is assessed by the skill against the detected dialect",
}

_RUNNERS = {
    "unfinished-markers": run_unfinished_markers,
    "secrets": run_secrets,
    "dependency-audit": run_dependency_audit,
    "repo-hygiene": run_repo_hygiene,
    "dead-code": run_dead_code,
}


def _reference_findings(ctx: Ctx, family) -> tuple[FamilyResult, set[str]]:
    """Delegate the docs family to the reference checker, when it is reachable.

    The two plugins install separately, so this is the same ladder problem as stack
    detection: use the real checker when it is there, and say so honestly when it is
    not, rather than shipping a second weaker copy of it.
    """
    from checks import _run

    candidates = [
        Path(__file__).resolve().parents[2] / "engineering-lifecycle" / "scripts" / "reference-check.py",
        ctx.root / "engineering-lifecycle" / "scripts" / "reference-check.py",
    ]
    script = next((path for path in candidates if path.is_file()), None)
    if script is None:
        return (
            FamilyResult(
                id=family.id,
                title=family.title,
                outcome="not-checked",
                reason="the reference checker ships with engineering-lifecycle, which is not installed alongside this plugin",
            ),
            set(),
        )
    outcome = _run(f'"{sys.executable}" -B "{script}" --root .', ctx.root)
    if not outcome.get("output"):
        # Empty output used to parse as `{}`, which made `checked` default True and
        # `errors` default empty - so a reference checker whose output was lost, or
        # which never ran, rendered as a clean docs pass. There is no reading of
        # "no output at all" that is evidence of anything.
        return (
            FamilyResult(
                id=family.id,
                title=family.title,
                outcome="errored",
                reason=(
                    "the reference checker produced no output: "
                    + str(outcome.get("error") or ("it timed out" if outcome.get("timed_out") else "reason unknown"))
                ),
                commands=[{k: v for k, v in outcome.items() if k != "output"}],
            ),
            set(),
        )
    try:
        payload = json.loads(outcome["output"])
    except ValueError:
        return (
            FamilyResult(
                id=family.id,
                title=family.title,
                outcome="errored",
                reason="the reference checker produced output that could not be parsed",
                commands=[{k: v for k, v in outcome.items() if k != "output"}],
            ),
            set(),
        )

    if not payload.get("checked", True):
        # The checker refuses a root with no plugin manifests under it, because its
        # namespaces would be empty and everything would read as unknown. That is a
        # not-checked, with its reason - not a clean pass.
        return (
            FamilyResult(
                id=family.id,
                title=family.title,
                outcome="not-checked",
                reason=str(payload.get("reason") or "the reference checker declined to run against this root"),
                commands=[{k: v for k, v in outcome.items() if k != "output"}],
            ),
            set(),
        )

    from findings import Evidence, Finding

    findings = [
        Finding(
            family=family.id,
            rule=f"reference/{item['rule']}",
            severity="warning" if item["severity"] == "error" else "suggestion",
            title=f"`{item['token']}` does not resolve",
            detail=item["message"],
            evidence=[Evidence(item["path"], item["line"], item["token"])],
            route={"kind": "agent", "target": family.route, "available": None},
            suggested_strategy="auto",
        )
        for item in payload.get("errors", []) + payload.get("warnings", [])
    ]
    unresolved = {item["token"] for item in payload.get("errors", []) + payload.get("warnings", [])}
    result = FamilyResult(
        id=family.id,
        title=family.title,
        outcome="failed" if findings else "passed",
        applies_because="markdown documents are present",
        commands=[{k: v for k, v in outcome.items() if k != "output"}],
        findings=findings,
    )
    return result, unresolved


def audit(
    root: Path,
    plan_path: Path | None,
    stamp: str,
    prefer: str = "",
    allow_untrusted_commands: bool = False,
) -> dict:
    stack = resolve_stack(root, prefer)
    files, scope_warning = collect_files(root)
    resolved_plan = plan_path or find_plan(root)
    plan = (
        parse_plan(resolved_plan, root)
        if resolved_plan and resolved_plan.is_file()
        else {"path": None, "parsed_by": None, "item_count": 0, "items": []}
    )
    ctx = Ctx(
        root=root,
        stack=stack,
        plan=plan,
        files=files,
        allow_untrusted_commands=allow_untrusted_commands,
    )

    results: list[FamilyResult] = []
    unresolved: set[str] = set()
    for family in REGISTRY:
        relevant, why = family.applies_when(ctx)
        if not relevant:
            results.append(FamilyResult(id=family.id, title=family.title, outcome="not-applicable", reason=why))
            continue
        runnable, blocker = family.requires(ctx)
        if not runnable:
            results.append(
                FamilyResult(
                    id=family.id, title=family.title, outcome="not-checked", reason=blocker, applies_because=why
                )
            )
            continue

        if family.id in _MODEL_DRIVEN:
            results.append(
                FamilyResult(
                    id=family.id,
                    title=family.title,
                    outcome="not-checked",
                    reason=_MODEL_DRIVEN[family.id],
                    applies_because=why,
                )
            )
            continue
        if family.id == "docs-references":
            result, unresolved = _reference_findings(ctx, family)
            results.append(result)
            continue
        if family.id == "static-analysis":
            results.append(run_command_family(ctx, family, ("lint", "typecheck"), "warning"))
            continue
        if family.id == "tests":
            results.append(run_command_family(ctx, family, ("unit",), "critical"))
            continue
        if family.id == "build":
            results.append(run_command_family(ctx, family, ("build",), "critical"))
            continue
        if family.id == "plan-drift":
            results.append(_plan_drift(ctx, family, unresolved))
            continue
        runner = _RUNNERS.get(family.id)
        if runner is None:
            results.append(
                FamilyResult(
                    id=family.id,
                    title=family.title,
                    outcome="not-checked",
                    reason="registered but no runner is implemented",
                    applies_because=why,
                )
            )
            continue
        results.append(runner(ctx, family))

    mark_unverifiable(plan["items"], unresolved)
    document = build_document(
        run_id=stamp,
        generated_at=now_iso(),
        root=root.as_posix(),
        plan={"path": plan["path"], "parsed_by": plan["parsed_by"], "item_count": plan["item_count"]},
        stack=stack,
        results=results,
        plan_items=[item.as_dict() for item in plan["items"]],
    )
    if scope_warning:
        document["scope_warnings"] = [scope_warning]
    # `FamilyResult.validate` had never run outside the test suite, so its four
    # invariants - including "failed with no findings" and "passed with findings" -
    # had never been checked against a real run.
    problems = [problem for result in results for problem in result.validate()]
    problems += validate_document(document, registered_ids())
    if problems:
        document["validation_errors"] = problems
    return document


def _plan_drift(ctx: Ctx, family, unresolved: set[str]) -> FamilyResult:
    """Plan items naming artefacts that do not resolve.

    This is the join between the audit and the reference checker: an item promising
    a file nothing can find is neither done nor undone on the available evidence,
    and the report says exactly that instead of guessing.
    """
    from findings import Evidence, Finding

    findings = [
        Finding(
            family=family.id,
            rule="plan/unverifiable-item",
            severity="warning",
            title=f"Plan item {item.id} names something that does not resolve",
            detail=f"{item.title} - {item.reason or 'see mentions'}",
            evidence=[Evidence(item.source.split(":")[0], int(item.source.split(":")[-1] or 0) or None, item.title)],
            plan_items=[item.id],
            route={"kind": "skill", "target": family.route, "available": None},
            suggested_strategy="human-input",
        )
        for item in ctx.plan["items"]
        if any(token in unresolved for token in item.mentions)
    ]
    return FamilyResult(
        id=family.id,
        title=family.title,
        outcome="failed" if findings else "passed",
        applies_because=f"plan parsed by {ctx.plan['parsed_by']}",
        findings=findings,
    )


def main() -> int:
    # A Windows console defaults to a codepage that cannot encode the replacement
    # character, and captured output now legitimately contains one whenever a tool
    # emitted a byte UTF-8 could not decode. Printing a reason string through that
    # console would raise UnicodeEncodeError and lose the run. Degrade instead.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--plan", default="", help="Path to the plan. Discovered when omitted.")
    parser.add_argument("--prefer", default="", choices=["", "workspace", "imported", "vendored"])
    parser.add_argument("--stamp", default="", help="Override the run id. For tests.")
    parser.add_argument("--out", default="", help="Write into this directory instead of the canonical one.")
    parser.add_argument("--print", action="store_true", help="Emit the document on stdout and write nothing.")
    parser.add_argument(
        "--allow-untrusted-commands",
        action="store_true",
        help="Run check commands taken verbatim from the audited repository's own stack.json",
    )
    args = parser.parse_args()

    # An explicit --root is taken literally. Passing it through repo_root walks up to
    # the nearest .git or plugin manifest, which silently audits the parent project
    # instead of the directory named - and on a nested target that means the plan
    # sitting right there is invisible.
    root = Path(args.root).resolve() if args.root not in ("", ".") else repo_root(Path("."))
    stamp = run_id(args.stamp or None)
    plan_path = Path(args.plan) if args.plan else None
    if plan_path and not plan_path.is_absolute():
        plan_path = root / plan_path

    document = audit(root, plan_path, stamp, args.prefer, args.allow_untrusted_commands)
    if args.print:
        print(json.dumps(document, indent=2, sort_keys=True))
        return 1 if document.get("validation_errors") else 0

    target = Path(args.out) if args.out else audit_dir(root, stamp)
    write_json(target / "findings.json", document)

    from importlib import import_module

    render = import_module("render_report") if _has_module("render_report") else None
    if render is not None:
        write_text(target / "report.md", render.render(document))

    if document["plan"]["parsed_by"] is None:
        print(
            "No plan could be parsed. Nothing was audited against an inventory - "
            "pass --plan with the real plan document rather than accepting this run.",
            file=sys.stderr,
        )
    print(relpath(target / "findings.json", root))
    return 1 if document.get("validation_errors") else 0


def _has_module(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


if __name__ == "__main__":
    raise SystemExit(main())
