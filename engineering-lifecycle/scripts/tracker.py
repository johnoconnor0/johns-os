#!/usr/bin/env python3
"""The queue of surfaced issues, its settings, and the tracker round trip.

Hooks and CI cannot call MCP tools - only the model can. That constraint shaped
`linear-sync.py` and it shapes this: the deterministic half decides *what* should
happen and emits a plan; the model executes the plan through whichever MCP tools
exist; `reconcile` writes the returned ids back. Nothing here touches the network.

Three files, all under `.project/.engineering/`:

    settings.json                   hand-authored, committed, the only file in that
                                    tree that is not regenerable
    tracker/surfaced-issues.json    the queue, plus a generated .md digest
    tracker/dispatch-state.json     what has been filed, and which MCP server name
                                    turned out to work

The queue is modelled on `questions.py` rather than invented: stable hash ids so
re-detection updates instead of duplicating, a generated digest beside the JSON so
the folder is useful without a tool, and the rule that a filed item stays filed no
matter how often its source is rescanned.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from eng_common import (
    engineering_root,
    now_iso,
    read_json,
    read_json_safe,
    relpath,
    workspace_exists,
    write_json,
    write_text,
)
from trackers import Tracker, parse_scope_url, qualified_tool, resolve_tracker, tool_candidates

SEVERITIES = ("critical", "high", "medium", "low")
ISSUE_STATUSES = ("queued", "filing", "filed", "resolved", "dismissed", "duplicate")
KINDS = ("anomaly", "bug", "risk", "question", "task", "improvement")
ORIGINS = ("detector", "ledger", "model", "human", "skill")

SETTINGS_FILE = "settings.json"
_QUEUE = ("tracker", "surfaced-issues.json")
_DIGEST = ("tracker", "surfaced-issues.md")
_STATE = ("tracker", "dispatch-state.json")
_DISABLED = ("tracker", "DISABLED")

HASH_FIELDS = ("title", "body", "severity", "status")

DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "provider": "file",
    "enforcement": "remind",
    "dispatch": {"on_stop": True, "on_user_prompt": True, "min_severity": "medium", "max_per_turn": 10},
    "capture": {"detector": True, "ledger": True, "model": True},
    "mcp_server": None,
    "scope": {},
    "status_map": {},
    "assignee_map": {},
    "labels": [],
}


# --- paths -----------------------------------------------------------------


def settings_path(root: Path) -> Path:
    return engineering_root(root) / SETTINGS_FILE


def queue_path(root: Path) -> Path:
    return engineering_root(root).joinpath(*_QUEUE)


def digest_path(root: Path) -> Path:
    return engineering_root(root).joinpath(*_DIGEST)


def state_path(root: Path) -> Path:
    return engineering_root(root).joinpath(*_STATE)


def disabled_path(root: Path) -> Path:
    return engineering_root(root).joinpath(*_DISABLED)


def is_disabled(root: Path) -> bool:
    """The cheapest kill switch, checked before any JSON is parsed.

    A sentinel file rather than a settings key so that it still works when
    `settings.json` is malformed - which is exactly the moment you most want to be
    able to turn something off.
    """
    return disabled_path(root).exists()


# --- settings --------------------------------------------------------------


def _merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged


def _from_legacy(root: Path) -> dict[str, Any]:
    """`ledger/linear-config.json` mapped onto the new shape.

    Read, never deleted. An install that configured Linear before this existed keeps
    working, and the two existing regression tests for that path keep passing
    unmodified.
    """
    legacy = read_json_safe(engineering_root(root) / "ledger" / "linear-config.json")
    if not legacy:
        return {}
    scope = {key: legacy.get(key) for key in ("team", "project", "cycle") if legacy.get(key)}
    mapped: dict[str, Any] = {"provider": "linear", "scope": scope}
    for key in ("status_map", "assignee_map", "enforcement"):
        if legacy.get(key):
            mapped[key] = legacy[key]
    if legacy.get("label"):
        mapped["labels"] = [legacy["label"]]
    if scope.get("team") and scope["team"] != "unknown":
        mapped["enabled"] = True
    return mapped


def _from_env() -> dict[str, Any]:
    """The literal key names JOS-31 named, as the per-session override.

    Environment last on purpose: a file is where configuration lives, and an env var
    is how you override it for one session without editing anything.
    """
    overlay: dict[str, Any] = {}
    scope: dict[str, Any] = {}
    if os.environ.get("ISSUE_MANAGEMENT_SOFTWARE"):
        overlay["provider"] = os.environ["ISSUE_MANAGEMENT_SOFTWARE"]
    enabled = os.environ.get("ENABLE_ISSUE_FILING")
    if enabled is not None:
        overlay["enabled"] = enabled.strip().lower() in {"1", "true", "yes", "on"}
    if os.environ.get("ISSUE_TRACKER_MCP_SERVER"):
        overlay["mcp_server"] = os.environ["ISSUE_TRACKER_MCP_SERVER"]
    for name, key in (("LINEAR_PROJECT_ID", "project"), ("LINEAR_TEAM_ID", "team")):
        if os.environ.get(name):
            scope[key] = os.environ[name]
    if os.environ.get("LINEAR_PROJECT_URL"):
        scope["project_url"] = os.environ["LINEAR_PROJECT_URL"]
    if scope:
        overlay["scope"] = scope
    return overlay


def load_settings(root: Path, override: str | None = None) -> dict[str, Any]:
    """Effective settings, and the tracker they resolve to.

    Precedence, later wins: provider defaults, legacy linear-config.json,
    settings.json, environment.
    """
    legacy = _from_legacy(root)
    stored = read_json_safe(settings_path(root)).get("issue_filing", {})
    stored = stored if isinstance(stored, dict) else {}
    env = _from_env()
    resolved = _merge(_merge(_merge(DEFAULTS, legacy), stored), env)

    tracker, reason = resolve_tracker(root, resolved, override)
    # `resolve_tracker` sees only the merged result, so it cannot tell which layer
    # supplied the provider. Naming the wrong one would be a misleading provenance
    # string in the very field that exists to make the choice auditable.
    if not override:
        for layer, label in ((env, "ISSUE_MANAGEMENT_SOFTWARE"), (stored, "settings.json issue_filing.provider")):
            if layer.get("provider"):
                reason = f"{label}: {layer['provider']}"
                break
        else:
            if legacy.get("provider"):
                reason = "ledger/linear-config.json is present"
    resolved["provider"] = tracker.name
    resolved["provider_reason"] = reason
    # A pasted URL decodes into the same scope keys an id would have filled, so the
    # rest of the pipeline never has to know which the human supplied.
    url = resolved.get("scope", {}).get("project_url")
    if url:
        resolved["scope"] = {**parse_scope_url(tracker, url), **{k: v for k, v in resolved["scope"].items() if v}}
    resolved["status_map"] = {**tracker.default_status_map, **(resolved.get("status_map") or {})}
    if is_disabled(root):
        resolved["enabled"] = False
        resolved["disabled_by"] = relpath(disabled_path(root), root)
    return resolved


def tracker_for(root: Path, settings: Mapping[str, Any] | None = None, override: str | None = None) -> Tracker:
    resolved = settings if settings is not None else load_settings(root, override)
    return resolve_tracker(root, resolved, override)[0]


# --- the queue -------------------------------------------------------------


def issue_id(rule: str, title: str, path: str = "") -> str:
    """Stable id, so re-detecting the same thing updates rather than duplicates.

    Same construction as `question_id`, for the same reason: a detector runs on
    every edit, and an id derived from content is what stops that becoming a
    thousand rows.
    """
    normalised = " ".join((title or "").lower().split())
    return "si-" + hashlib.sha1(f"{rule}|{normalised}|{path}".encode()).hexdigest()[:12]


def issue_hash(issue: Mapping[str, Any]) -> str:
    """Changes only when something worth pushing changed. Mirrors `task_hash`."""
    payload = json.dumps({key: issue.get(key) for key in HASH_FIELDS}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_queue(root: Path) -> dict[str, Any]:
    data = read_json(queue_path(root)) or {}
    issues = data.get("issues")
    return {"generated_at": data.get("generated_at", now_iso()), "issues": issues if issues else []}


def _sorted_issues(issues: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    order = {name: index for index, name in enumerate(SEVERITIES)}
    return sorted(
        (dict(issue) for issue in issues),
        key=lambda item: (
            item.get("status") != "queued",
            order.get(item.get("severity", "medium"), 99),
            item.get("detected_at", ""),
        ),
    )


def render_digest(payload: Mapping[str, Any]) -> str:
    """A human-readable view beside the machine one, as `questions.py` does."""
    issues = payload.get("issues", [])
    lines = ["# Surfaced Issues", "", f"Generated at {payload.get('generated_at', '')}.", ""]
    for status in ISSUE_STATUSES:
        group = [issue for issue in issues if issue.get("status") == status]
        if not group:
            continue
        lines += [f"## {status.title()} ({len(group)})", ""]
        for issue in group:
            lines.append(f"- **{issue['title']}**")
            detail = f"  - id: `{issue['id']}` | severity: {issue.get('severity')} | origin: {issue.get('origin')}"
            if issue.get("rule"):
                detail += f" | rule: `{issue['rule']}`"
            lines.append(detail)
            if issue.get("paths"):
                lines.append(f"  - paths: {', '.join(f'`{path}`' for path in issue['paths'][:5])}")
            external = issue.get("external") or {}
            if external.get("url"):
                lines.append(f"  - filed: [{external.get('identifier') or external.get('id')}]({external['url']})")
        lines.append("")
    if not issues:
        lines += ["None recorded.", ""]
    return "\n".join(lines)


def record_issues(root: Path, entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Upsert by stable id, preserving everything the round trip established.

    A filed or dismissed issue stays that way no matter how often its detector runs
    again - the same invariant `record_questions` protects, and for the same reason:
    without it the next scan silently reopens work a human already dealt with.
    """
    store = load_queue(root)
    existing = {issue["id"]: dict(issue) for issue in store["issues"] if issue.get("id")}
    for entry in entries:
        title = str(entry.get("title", "")).strip()
        if not title:
            continue
        rule = str(entry.get("rule") or entry.get("kind") or "manual")
        paths = [str(item) for item in (entry.get("paths") or []) if str(item).strip()]
        identifier = str(entry.get("id") or issue_id(rule, title, paths[0] if paths else ""))
        record: dict[str, Any] = {
            "id": identifier,
            "title": title,
            "body": str(entry.get("body", "")),
            "kind": entry.get("kind") if entry.get("kind") in KINDS else "anomaly",
            "severity": entry.get("severity") if entry.get("severity") in SEVERITIES else "medium",
            "status": entry.get("status") if entry.get("status") in ISSUE_STATUSES else "queued",
            "origin": entry.get("origin") if entry.get("origin") in ORIGINS else "model",
            "rule": rule,
            "paths": paths,
            "detected_at": now_iso(),
            "last_seen_at": now_iso(),
            "occurrences": 1,
        }
        for optional in ("initiative_id", "external", "source"):
            if entry.get(optional) is not None:
                record[optional] = entry[optional]

        previous = existing.get(identifier)
        if previous:
            record["detected_at"] = previous.get("detected_at", record["detected_at"])
            record["occurrences"] = int(previous.get("occurrences", 1)) + 1
            if previous.get("external"):
                record["external"] = previous["external"]
            if previous.get("status") in {"filed", "resolved", "dismissed", "duplicate"}:
                record["status"] = previous["status"]
        record["hash"] = issue_hash(record)
        existing[identifier] = record

    payload = {"generated_at": now_iso(), "issues": _sorted_issues(existing.values())}
    if workspace_exists(root):
        write_json(queue_path(root), payload)
        write_text(digest_path(root), render_digest(payload))
    return payload


def set_status(root: Path, identifier: str, status: str, note: str = "") -> dict[str, Any]:
    store = load_queue(root)
    for issue in store["issues"]:
        if issue.get("id") != identifier:
            continue
        if status not in ISSUE_STATUSES:
            return {"updated": False, "reason": f"unknown status {status!r}"}
        issue["status"] = status
        if note:
            issue["note"] = note
        store["generated_at"] = now_iso()
        store["issues"] = _sorted_issues(store["issues"])
        if workspace_exists(root):
            write_json(queue_path(root), store)
            write_text(digest_path(root), render_digest(store))
        return {"updated": True, "issue": issue}
    return {"updated": False, "reason": f"no queued issue with id {identifier!r}"}


# --- the ledger adapter ----------------------------------------------------


def items_from_ledger(root: Path) -> list[dict[str, Any]]:
    """Ledger action items and human tasks, as queue entries.

    Globbed across the whole workspace rather than read from one canonical path,
    matching `sync-ledger.py`. Reading only `ledger/action-items.json` is what made
    items written into an initiative folder invisible to tracker sync.
    """
    workspace = engineering_root(root)
    if not workspace.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for pattern, list_key, title_key, kind in (
        ("*action-items*.json", "action_items", "title", "task"),
        ("*human-tasks*.json", "human_tasks", "task", "task"),
    ):
        for path in sorted(workspace.rglob(pattern)):
            data = read_json(path, {})
            items = data if isinstance(data, list) else (data or {}).get(list_key, [])
            for item in items:
                if not isinstance(item, dict) or item.get("status") == "done":
                    continue
                entries.append(
                    {
                        "id": f"si-ledger-{item.get('id')}",
                        "title": str(item.get(title_key) or "Untitled"),
                        "body": str(item.get("description") or item.get("reason") or item.get("source") or ""),
                        "kind": kind,
                        "severity": "medium",
                        "origin": "ledger",
                        "rule": f"ledger/{list_key}",
                        "paths": [relpath(path, root)],
                        "external": {"id": item.get("linear_id"), "url": item.get("linear_url")}
                        if item.get("linear_id")
                        else None,
                    }
                )
    return entries


# --- the plan / reconcile round trip ---------------------------------------


def _severity_at_least(severity: str, minimum: str) -> bool:
    order = {name: index for index, name in enumerate(SEVERITIES)}
    return order.get(severity, 99) <= order.get(minimum, 99)


def build_plan(root: Path, override: str | None = None) -> dict[str, Any]:
    """Operations the model should execute, with the arguments already mapped."""
    settings = load_settings(root, override)
    tracker = tracker_for(root, settings, override)
    state = read_json_safe(state_path(root))
    server = settings.get("mcp_server") or state.get("mcp_server")
    minimum = settings.get("dispatch", {}).get("min_severity", "medium")

    operations: list[dict[str, Any]] = []
    for issue in load_queue(root)["issues"]:
        if issue.get("status") not in {"queued", "filing"}:
            continue
        if not _severity_at_least(issue.get("severity", "medium"), minimum):
            continue
        external = issue.get("external") or {}
        action = "update" if external.get("id") else "create"
        verb = tracker.update_tool if action == "update" else tracker.create_tool

        arguments: dict[str, Any] = {}
        if tracker.remote:
            arguments[tracker.field_argument("title")] = f"[{issue['severity']}] {issue['title']}"
            arguments[tracker.field_argument("body")] = _issue_body(issue)
            mapped_status = settings["status_map"].get("open", "open")
            arguments[tracker.field_argument("status")] = mapped_status
            for key, value in (settings.get("scope") or {}).items():
                if value and key != "project_url":
                    arguments[tracker.scope_argument(key)] = value
            if tracker.supports_labels and settings.get("labels"):
                arguments[tracker.field_argument("labels")] = list(settings["labels"])
            priority = tracker.priority_map.get(issue.get("severity", "medium"))
            if priority is not None:
                arguments[tracker.field_argument("priority")] = priority
            if action == "update":
                arguments[tracker.update_key] = external["id"]

        operations.append(
            {
                "key": issue["id"],
                "action": action,
                "severity": issue["severity"],
                "title": issue["title"],
                "hash": issue.get("hash") or issue_hash(issue),
                "tool": qualified_tool(tracker, verb, server),
                "tool_candidates": tool_candidates(tracker, verb, server),
                "arguments": arguments,
                # Where to read the ids out of whatever the tool returns.
                "result_map": {"id": tracker.id_key, "url": tracker.url_key, "identifier": tracker.identifier_key},
            }
        )

    return {
        "generated_at": now_iso(),
        "configured": bool(settings.get("enabled")) and tracker.remote,
        "enabled": bool(settings.get("enabled")),
        "provider": tracker.name,
        "provider_reason": settings.get("provider_reason", ""),
        "mcp_server": server,
        "scope": settings.get("scope", {}),
        "min_severity": minimum,
        "operations": operations,
        "note": (
            ""
            if tracker.remote
            else "The local file provider does not file anywhere. Issues stay in the queue and its digest."
        ),
    }


def _issue_body(issue: Mapping[str, Any]) -> str:
    """The issue description, carrying an identity marker for cross-machine dedup.

    `.project/` is gitignored, so `dispatch-state.json` is per-machine and a second
    machine would otherwise re-create every issue. The marker means deduplication
    depends on the tracker's own contents rather than on a file that does not travel.
    """
    lines = [issue.get("body", "").strip() or issue["title"]]
    if issue.get("paths"):
        lines += ["", "Paths:", *[f"- `{path}`" for path in issue["paths"][:10]]]
    if issue.get("rule"):
        lines += ["", f"Detected by rule `{issue['rule']}` ({issue.get('origin', 'unknown')})."]
    lines += ["", f"<!-- jos-issue: {issue['id']} -->"]
    return "\n".join(lines)


def reconcile(root: Path, results: Iterable[Mapping[str, Any]], server: str | None = None) -> dict[str, Any]:
    """Write returned ids back into the queue, and remember the server that worked."""
    store = load_queue(root)
    by_id = {issue["id"]: issue for issue in store["issues"]}
    applied = 0
    for result in results:
        issue = by_id.get(str(result.get("key", "")))
        if issue is None or not result.get("id"):
            continue
        issue["external"] = {
            "provider": result.get("provider") or "",
            "id": result.get("id"),
            "url": result.get("url"),
            "identifier": result.get("identifier"),
            "synced_at": now_iso(),
        }
        issue["status"] = "filed"
        applied += 1
    store["generated_at"] = now_iso()
    store["issues"] = _sorted_issues(store["issues"])

    state = read_json_safe(state_path(root))
    if server:
        state["mcp_server"] = server
    state["last_dispatch_at"] = now_iso()
    state["filed_count"] = int(state.get("filed_count", 0)) + applied
    if workspace_exists(root):
        write_json(queue_path(root), store)
        write_text(digest_path(root), render_digest(store))
        write_json(state_path(root), state)
    return {"reconciled": applied, "mcp_server": state.get("mcp_server")}


def tracker_status(root: Path) -> dict[str, Any]:
    """The one-line answer the intake hook needs, with no network and no MCP."""
    if not workspace_exists(root):
        return {"checked": False, "reason": "no lifecycle workspace", "enabled": False, "queued": 0}
    settings = load_settings(root)
    issues = load_queue(root)["issues"]
    minimum = settings.get("dispatch", {}).get("min_severity", "medium")
    queued = [
        issue
        for issue in issues
        if issue.get("status") == "queued" and _severity_at_least(issue.get("severity", "medium"), minimum)
    ]
    below = sum(1 for issue in issues if issue.get("status") == "queued") - len(queued)
    return {
        "checked": True,
        "enabled": bool(settings.get("enabled")),
        "provider": settings.get("provider"),
        "enforcement": settings.get("enforcement", "remind"),
        "queued": len(queued),
        # Surfaced so the intake count and the report count can be reconciled. A
        # filter that silently drops findings is how two numbers come to disagree
        # and somebody files a bug about it.
        "below_min_severity": max(0, below),
        "min_severity": minimum,
        "filed": sum(1 for issue in issues if issue.get("status") == "filed"),
        "titles": [issue["title"] for issue in queued[:3]],
    }
