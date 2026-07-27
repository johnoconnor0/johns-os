#!/usr/bin/env python3
"""SessionStart: recall what this project has already decided.

Dormant until the workspace is opted in, and never creates it. Renders a compact
digest rather than the raw JSON — the point is to start a session already knowing
the stack, the accepted decisions and the open initiatives, so the model does not
re-derive them or contradict them.

Capped hard: a memory primer that floods the context window costs more than it
saves.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import emit_json, hook_additional_context, repo_root, workspace_exists
from quality_tools import load_project_memory

MAX_CHARS = 2_000


def render(memory: dict) -> str:
    lines: list[str] = []

    stack = (memory.get("profile") or {}).get("stack") or {}
    parts = [
        f"{label}: {', '.join(stack[key])}"
        for key, label in (
            ("frameworks", "frameworks"),
            ("backend", "backend"),
            ("database", "database"),
            ("testing", "testing"),
        )
        if stack.get(key)
    ]
    if stack.get("package_manager"):
        parts.insert(0, f"package manager: {stack['package_manager']}")
    if parts:
        lines.append("Stack - " + "; ".join(parts) + ".")

    initiatives = memory.get("initiatives") or []
    if initiatives:
        described = ", ".join(f"{item['id']} ({item['stage_count']} stages)" for item in initiatives)
        lines.append(f"Initiatives on record: {described}.")

    decisions = memory.get("decisions") or []
    if decisions:
        lines.append("Decisions already made (do not re-litigate without reason):")
        for entry in decisions:
            title = entry.get("title") or Path(entry["path"]).stem
            lines.append(f"  - [{entry.get('status', 'unknown')}] {title}: {entry.get('summary', '')}".rstrip(": "))

    summary = memory.get("ledger") or {}
    open_items = summary.get("open_action_item_count", 0)
    open_tasks = summary.get("open_human_task_count", 0)
    if open_items or open_tasks:
        lines.append(f"Ledger: {open_items} open action item(s), {open_tasks} open human task(s).")

    if not lines:
        return ""
    body = "\n".join(lines)
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS].rsplit("\n", 1)[0] + "\n  (truncated)"
    return "Engineering Lifecycle project memory:\n" + body


def main() -> int:
    root = repo_root()
    if not workspace_exists(root):
        return 0
    message = render(load_project_memory(root))
    if not message:
        return 0
    emit_json(hook_additional_context("SessionStart", message))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
