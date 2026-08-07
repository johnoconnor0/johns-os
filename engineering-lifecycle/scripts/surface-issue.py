#!/usr/bin/env python3
"""Record and file issues surfaced during a session.

The deterministic half of issue filing. Hooks cannot call MCP tools, so `plan`
emits the operations and the model executes them; `reconcile` writes the returned
ids back. Same division `linear-sync.py` established, now provider-agnostic.

    record      add one issue to the queue (this is the one-liner the model uses)
    list        show the queue
    status      the counts, for a hook or a human
    plan        emit the operations to execute through MCP
    reconcile   write returned ids back
    resolve     mark an issue resolved or dismissed
    init        write a starter settings.json
    on / off    the kill switch
"""

from __future__ import annotations

import argparse
from pathlib import Path

from eng_common import emit_json, read_json, relpath, repo_root, resolve_cli_root, workspace_exists, write_json
from tracker import (
    DEFAULT_FETCH_LIMIT,
    ISSUE_STATUSES,
    KINDS,
    SEVERITIES,
    build_fetch_plan,
    build_plan,
    disabled_path,
    ingest_issues,
    items_from_ledger,
    load_queue,
    load_settings,
    reconcile,
    record_issues,
    set_status,
    settings_path,
    tracker_status,
)

_STARTER = {
    "$comment": (
        "Issue filing for this project. The one hand-authored, committed file under "
        ".project/.engineering/ - everything else in that tree is regenerable. "
        "Env vars override these per session: ISSUE_MANAGEMENT_SOFTWARE, "
        "ENABLE_ISSUE_FILING, LINEAR_PROJECT_ID, LINEAR_PROJECT_URL, LINEAR_TEAM_ID, "
        "ISSUE_TRACKER_MCP_SERVER."
    ),
    "version": 1,
    "issue_filing": {
        "enabled": False,
        "provider": "file",
        "enforcement": "remind",
        "dispatch": {"on_stop": True, "on_user_prompt": True, "min_severity": "medium", "max_per_turn": 10},
        "capture": {"detector": True, "ledger": True, "model": True},
        "mcp_server": None,
        "scope": {},
        "status_map": {},
        "labels": [],
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--provider", default="", help="Override the configured provider for this call")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="Add one surfaced issue to the queue.")
    record.add_argument("--title", required=True)
    record.add_argument("--body", default="")
    record.add_argument("--severity", default="medium", choices=list(SEVERITIES))
    record.add_argument("--kind", default="anomaly", choices=list(KINDS))
    record.add_argument("--rule", default="manual")
    record.add_argument("--path", action="append", default=[], help="Repeatable")
    record.add_argument("--origin", default="model")

    sub.add_parser("list", help="Print the queue.")
    sub.add_parser("status", help="Print the counts.")
    sub.add_parser("pending", help="Print how many issues are waiting to be filed.")

    plan_parser = sub.add_parser("plan", help="Emit the operations for the model to execute via MCP.")
    plan_parser.add_argument("--include-ledger", action="store_true", help="Fold ledger tasks into the queue first")

    reconcile_parser = sub.add_parser("reconcile", help="Write returned issue ids back into the queue.")
    reconcile_parser.add_argument("--results", required=True, help="JSON file: [{key, id, url, identifier}]")
    reconcile_parser.add_argument("--mcp-server", default="", help="The server segment that actually worked")

    fetch_parser = sub.add_parser("fetch-plan", help="Emit the search operations that pull open work back.")
    fetch_parser.add_argument("--limit", type=int, default=DEFAULT_FETCH_LIMIT)
    fetch_parser.add_argument("--state", action="append", default=[], help="Repeatable; defaults to every open state")
    fetch_parser.add_argument("--updated-since", default="", help="ISO date or duration, e.g. -P30D")

    ingest_parser = sub.add_parser("ingest", help="Fold tracker search results into the queue.")
    ingest_parser.add_argument("--results", required=True, help="JSON file: {issues: [...]} or a bare list")
    ingest_parser.add_argument("--mcp-server", default="", help="The server segment that actually worked")

    resolve = sub.add_parser("resolve", help="Mark an issue resolved or dismissed.")
    resolve.add_argument("--id", required=True)
    resolve.add_argument("--status", default="resolved", choices=list(ISSUE_STATUSES))
    resolve.add_argument("--note", default="")

    sub.add_parser("init", help="Write a starter settings.json if none exists.")
    sub.add_parser("on", help="Remove the DISABLED sentinel.")
    sub.add_parser("off", help="Create the DISABLED sentinel.")

    args = parser.parse_args()
    root = resolve_cli_root(args.root).root
    override = args.provider or None

    if args.command == "record":
        if not workspace_exists(root):
            emit_json({"recorded": 0, "reason": "no lifecycle workspace; run /project-init first"})
            return 0
        payload = record_issues(
            root,
            [
                {
                    "title": args.title,
                    "body": args.body,
                    "severity": args.severity,
                    "kind": args.kind,
                    "rule": args.rule,
                    "paths": args.path,
                    "origin": args.origin,
                }
            ],
        )
        emit_json({"recorded": 1, "queued": sum(1 for i in payload["issues"] if i["status"] == "queued")})
        return 0

    if args.command == "list":
        emit_json(load_queue(root))
        return 0
    if args.command == "status":
        emit_json(tracker_status(root))
        return 0
    if args.command == "pending":
        status = tracker_status(root)
        emit_json({"pending": status.get("queued", 0) > 0, "count": status.get("queued", 0)})
        return 0

    if args.command == "plan":
        if args.include_ledger and load_settings(root).get("capture", {}).get("ledger", True):
            record_issues(root, items_from_ledger(root))
        emit_json(build_plan(root, override))
        return 0

    if args.command == "reconcile":
        results = read_json(Path(args.results), [])
        emit_json(reconcile(root, results if isinstance(results, list) else [], args.mcp_server or None))
        return 0

    if args.command == "fetch-plan":
        emit_json(build_fetch_plan(root, override, args.limit, args.state or None, args.updated_since))
        return 0

    if args.command == "ingest":
        if not workspace_exists(root):
            emit_json({"ingested": 0, "reason": "no lifecycle workspace; run /project-init first"})
            return 0
        emit_json(ingest_issues(root, read_json(Path(args.results), {}), args.mcp_server or None))
        return 0

    if args.command == "resolve":
        emit_json(set_status(root, args.id, args.status, args.note))
        return 0

    if args.command == "init":
        target = settings_path(root)
        if target.exists():
            emit_json({"created": False, "path": relpath(target, root), "reason": "already exists; not overwritten"})
            return 0
        if not workspace_exists(root):
            emit_json({"created": False, "reason": "no lifecycle workspace; run /project-init first"})
            return 0
        write_json(target, _STARTER)
        emit_json({"created": True, "path": relpath(target, root), "next": "set provider, scope and enabled"})
        return 0

    if args.command in {"on", "off"}:
        sentinel = disabled_path(root)
        if args.command == "off":
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text(
                "Issue filing is off. Delete this file, or run `eng-life tracker on`, to re-enable it.\n",
                encoding="utf-8",
            )
        elif sentinel.exists():
            sentinel.unlink()
        emit_json({"enabled": args.command == "on", "sentinel": relpath(sentinel, root)})
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
