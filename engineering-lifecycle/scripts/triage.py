#!/usr/bin/env python3
"""Compile the issue queue into workstreams and emit a per-workstream agent plan.

The mirror of `surface-issue.py`: deterministic Python decides *what* should
happen and emits a plan, and the model executes it. A script cannot spawn an
agent for the same reason it cannot call an MCP tool, so the fan-out is the
model's job - but the prompts, the routing and the ordering are computed here,
which makes a dispatch reproducible and diffable rather than improvised.

## What the agents can actually do

Every lifecycle agent declares `tools: Read, Glob, Grep`. So the fan-out is an
*analysis* pass: root cause, affected files, risk, sequencing, test gaps. That is
the expensive thinking and it genuinely parallelises. The writing happens
afterwards, on the main thread, one workstream at a time through
implement-feature-safely.

Two consequences worth stating plainly, because both look like bugs otherwise:

- `parallel_safe` does **not** gate the analysis phase. Read-only agents cannot
  collide, so gating on it would halve the throughput this exists to provide.
- Implementation is serial for a concrete reason, not caution:
  `.project/.engineering/lifecycle/current-plan.json` is a single file, so two
  concurrent implementations clobber each other's edit-scope allowlist and the
  edit-scope guard silently goes inert for the loser of the race.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from eng_common import emit_json, engineering_root, plugin_root, relpath, resolve_cli_root, workspace_exists
from tracker import load_queue
from workstreams import (
    MAX_WORKSTREAM_SIZE,
    MERGE_THRESHOLD,
    build_workstreams,
    load_workstreams,
    workstream_status,
    write_workstreams,
)

DEFAULT_CONCURRENCY = 4


def _issue_lookup(root: Path) -> dict[str, dict[str, Any]]:
    return {issue["id"]: issue for issue in load_queue(root)["issues"]}


def _render_prompt(stream: dict[str, Any], issues: list[dict[str, Any]], root: Path) -> str:
    """A self-contained brief for one read-only advisor.

    Rendered here rather than composed by the model per task: six improvised
    prompts cost six round trips and are not reproducible between runs.
    """
    lines = [
        f"You are analysing one workstream from a triaged backlog: **{stream['title']}**.",
        "",
        "You have read-only tools. Do not attempt to edit anything; produce the analysis that",
        "makes the implementation obvious to whoever does it next.",
        "",
        f"Severity: {stream['severity']}. {len(issues)} issue(s) in this workstream.",
        "",
        "## Issues",
        "",
    ]
    for issue in issues:
        external = issue.get("external") or {}
        label = external.get("identifier") or issue["id"]
        lines.append(f"### {label} — {issue['title']}")
        if external.get("url"):
            lines.append(f"<{external['url']}>")
        body = (issue.get("body") or "").strip()
        if body:
            lines += ["", body[:2000]]
        lines.append("")
    if stream["paths"]:
        lines += [
            "## Files these issues name",
            "",
            *[f"- `{path}`" for path in stream["paths"][:20]],
            "",
            f"(Evidence: {stream['path_evidence']}. "
            + (
                "These were extracted from issue text and verified to exist; treat them as a starting point, not a "
                "complete list."
                if stream["path_evidence"] == "derived"
                else "Declared by the detector that surfaced the issue."
            ),
            "",
        ]
    lines += [
        "## Return",
        "",
        "Markdown with exactly these sections:",
        "",
        "## Root Cause",
        "## Affected Files",
        "## Proposed Sequence",
        "## Risks And Rollback",
        "## Test Gaps",
        "## Open Questions",
        "",
        "Rules:",
        "- Read the actual files before claiming anything about them.",
        "- If two issues here turn out to be unrelated, say so — the grouping is a heuristic.",
        "- Do not claim a check passed unless you ran it. You cannot run anything, so say what should be run.",
    ]
    return "\n".join(lines)


def build_dispatch_plan(root: Path, wave: int = 0, concurrency: int = DEFAULT_CONCURRENCY) -> dict[str, Any]:
    payload = load_workstreams(root)
    streams = payload.get("workstreams", []) if isinstance(payload, dict) else []
    if not streams:
        return {
            "generated_at": payload.get("generated_at", "") if isinstance(payload, dict) else "",
            "mode": "analysis",
            "wave": wave,
            "tasks": [],
            "deferred": [],
            "reason": "no workstreams; run `triage.py compile` first",
        }

    issues = _issue_lookup(root)
    agents_dir = plugin_root() / "agents"
    output_base = engineering_root(root) / "triage" / "analysis"

    tasks: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for stream in streams:
        if stream.get("wave", 0) != wave:
            deferred.append({"key": stream["id"], "reason": f"wave {stream.get('wave', 0)}, not {wave}"})
            continue
        members = [issues[key] for key in stream["issue_ids"] if key in issues]
        if not members:
            continue
        agent = stream["suggested_agent"]
        if not (agents_dir / f"{agent}.md").is_file():
            agent = "general-purpose"
        tasks.append(
            {
                "key": stream["id"],
                "agent": agent,
                "wave": stream.get("wave", 0),
                # Reported, deliberately not used as a filter. See the module docstring.
                "parallel_safe": stream["parallel_safe"],
                "output_path": relpath(output_base / f"{stream['id']}.md", root),
                "context_paths": stream["paths"][:20],
                "issue_refs": [
                    {
                        "id": issue["id"],
                        "identifier": (issue.get("external") or {}).get("identifier", ""),
                        "url": (issue.get("external") or {}).get("url", ""),
                        "title": issue["title"],
                        "severity": issue.get("severity", "medium"),
                    }
                    for issue in members
                ],
                "prompt": _render_prompt(stream, members, root),
            }
        )

    return {
        "generated_at": payload.get("generated_at", ""),
        "mode": "analysis",
        "wave": wave,
        "concurrency": concurrency,
        "tasks": tasks,
        "deferred": deferred,
        "write_phase": {
            "allowed": False,
            "reason": (
                "Every lifecycle agent declares tools: Read, Glob, Grep. Implementation happens on the main "
                "thread, one workstream at a time, through implement-feature-safely - current-plan.json is a "
                "single file, so concurrent implementations disable each other's edit-scope guard."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    compile_parser = sub.add_parser("compile", help="(Re)build workstreams from the queue.")
    compile_parser.add_argument("--threshold", type=float, default=MERGE_THRESHOLD)
    compile_parser.add_argument("--max-size", type=int, default=MAX_WORKSTREAM_SIZE)
    compile_parser.add_argument("--dry-run", action="store_true", help="Print without writing")

    sub.add_parser("list", help="Print the current workstreams.")
    sub.add_parser("status", help="Counts: workstreams, unclustered issues, staleness.")

    dispatch = sub.add_parser("dispatch-plan", help="Emit one agent task per workstream in a wave.")
    dispatch.add_argument("--wave", type=int, default=0)
    dispatch.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)

    args = parser.parse_args()
    root = resolve_cli_root(args.root).root

    if args.command == "compile":
        payload = build_workstreams(root, args.threshold, args.max_size)
        if not args.dry_run:
            if not workspace_exists(root):
                emit_json({"compiled": 0, "reason": "no lifecycle workspace; run /project-init first"})
                return 0
            write_workstreams(root, payload)
        emit_json(
            {
                "compiled": len(payload["workstreams"]),
                "clustered": payload["source"]["clustered"],
                "truncated": payload["truncated"],
                "workstreams": [
                    {
                        "id": stream["id"],
                        "title": stream["title"],
                        "severity": stream["severity"],
                        "size": stream["size"],
                        "agent": stream["suggested_agent"],
                        "parallel_safe": stream["parallel_safe"],
                        "title_confidence": stream["title_confidence"],
                    }
                    for stream in payload["workstreams"]
                ],
            }
        )
        return 0

    if args.command == "list":
        emit_json(load_workstreams(root))
        return 0

    if args.command == "status":
        emit_json(workstream_status(root))
        return 0

    if args.command == "dispatch-plan":
        emit_json(build_dispatch_plan(root, args.wave, args.concurrency))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
