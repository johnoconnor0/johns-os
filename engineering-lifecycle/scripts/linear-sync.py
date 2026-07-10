#!/usr/bin/env python3
"""Deterministic Linear task sync engine (no MCP).

Hooks and CI cannot call MCP tools — only the model can. So this script does the
deterministic half of Linear sync: it compares the local ledger tasks
(action-items + human-tasks) against the last-known Linear state and emits a
`plan` the model executes via the Linear MCP; `reconcile` writes the returned
issue ids back into the ledger; and `apply-pull` applies pulled status changes.

Canonical files (under <repo>/.project/.engineering/ledger/):
  action-items.json, human-tasks.json  — the tasks (source of truth for content)
  linear-config.json                    — team/project/status_map/enforcement
  linear-state.json                     — local key -> {linear_id, linear_url, hash}
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from eng_common import engineering_root, now_iso, read_json, repo_root, write_json

PRIORITY_MAP = {"urgent": 1, "high": 2, "normal": 3, "low": 4}
HASH_FIELDS = ("title", "status", "owner", "priority", "description")


def _ledger(root: Path) -> Path:
    return engineering_root(root) / "ledger"


def load_config(root: Path) -> dict:
    return read_json(_ledger(root) / "linear-config.json", {}) or {}


def load_state(root: Path) -> dict:
    state = read_json(_ledger(root) / "linear-state.json", {"tasks": {}})
    if not isinstance(state, dict) or "tasks" not in state:
        state = {"tasks": {}}
    return state


def _items(data, list_key: str) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get(list_key, [])
    return []


def load_tasks(root: Path) -> list[dict]:
    ledger = _ledger(root)
    tasks: list[dict] = []
    for item in _items(read_json(ledger / "action-items.json", {}), "action_items"):
        tasks.append(
            {
                "key": f"action:{item.get('id')}",
                "kind": "action",
                "id": item.get("id"),
                "title": item.get("title") or "Untitled",
                "status": item.get("status", "open"),
                "owner": item.get("owner"),
                "priority": item.get("priority", "normal"),
                "description": item.get("description") or item.get("source", ""),
                "linear_id": item.get("linear_id"),
            }
        )
    for item in _items(read_json(ledger / "human-tasks.json", {}), "human_tasks"):
        tasks.append(
            {
                "key": f"human:{item.get('id')}",
                "kind": "human",
                "id": item.get("id"),
                "title": item.get("task") or "Untitled",
                "status": item.get("status", "open"),
                "owner": item.get("owner"),
                "priority": "normal",
                "description": item.get("reason", ""),
                "linear_id": item.get("linear_id"),
            }
        )
    return tasks


def task_hash(task: dict) -> str:
    payload = json.dumps({k: task.get(k) for k in HASH_FIELDS}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_plan(root: Path) -> dict:
    config = load_config(root)
    state = load_state(root)["tasks"]
    status_map = config.get("status_map", {}) or {}
    plan = []
    for task in load_tasks(root):
        digest = task_hash(task)
        known = state.get(task["key"])
        linear_id = task.get("linear_id") or (known or {}).get("linear_id")
        if known is None and not task.get("linear_id"):
            action = "create"
        elif known is not None and known.get("hash") == digest:
            continue  # unchanged
        else:
            action = "update"
        plan.append(
            {
                "key": task["key"],
                "kind": task["kind"],
                "id": task["id"],
                "action": action,
                "linear_id": linear_id,
                "title": task["title"],
                "status": task["status"],
                "linear_state": status_map.get(task["status"], task["status"]),
                "owner": task["owner"],
                "priority": PRIORITY_MAP.get(task.get("priority", "normal"), 3),
                "description": task["description"],
                "hash": digest,
            }
        )
    return {
        "generated_at": now_iso(),
        "config_present": bool(config),
        "team": config.get("team"),
        "project": config.get("project"),
        "cycle": config.get("cycle"),
        "label": config.get("label"),
        "plan": plan,
    }


def _update_ledger_item(root: Path, kind: str, item_id: str, updates: dict) -> bool:
    fname = "action-items.json" if kind == "action" else "human-tasks.json"
    list_key = "action_items" if kind == "action" else "human_tasks"
    path = _ledger(root) / fname
    data = read_json(path, None)
    if not isinstance(data, dict) or list_key not in data:
        return False
    changed = False
    for item in data[list_key]:
        if item.get("id") == item_id:
            item.update(updates)
            changed = True
    if changed:
        write_json(path, data)
    return changed


def reconcile(root: Path, results: list[dict]) -> dict:
    state = load_state(root)
    tasks_by_key = {t["key"]: t for t in load_tasks(root)}
    applied = 0
    for result in results:
        key = result.get("key")
        linear_id = result.get("linear_id")
        if not key or not linear_id:
            continue
        kind, _, item_id = key.partition(":")
        task = tasks_by_key.get(key)
        digest = task_hash(task) if task else result.get("hash", "")
        state["tasks"][key] = {
            "linear_id": linear_id,
            "linear_url": result.get("linear_url"),
            "hash": digest,
            "kind": kind,
        }
        _update_ledger_item(root, kind, item_id, {"linear_id": linear_id, "linear_url": result.get("linear_url")})
        applied += 1
    write_json(_ledger(root) / "linear-state.json", state)
    return {"reconciled": applied}


def apply_pull(root: Path, updates: list[dict]) -> dict:
    # Pull is STATUS-ONLY: never overwrites local content, only the status field,
    # so a human status change in Linear reconciles without clobbering the ledger.
    applied = 0
    for update in updates:
        key = update.get("key")
        status = update.get("status")
        if not key or not status:
            continue
        kind, _, item_id = key.partition(":")
        if _update_ledger_item(root, kind, item_id, {"status": status}):
            applied += 1
    return {"pulled": applied}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="Emit the push plan (create/update) for the model to execute via MCP.")
    sub.add_parser("pending", help="Print how many tasks need pushing (for hooks).")
    reconcile_parser = sub.add_parser("reconcile", help="Write returned Linear ids back into the ledger.")
    reconcile_parser.add_argument("--results", required=True, help="JSON file: [{key, linear_id, linear_url}]")
    pull_parser = sub.add_parser("apply-pull", help="Apply pulled Linear statuses to local tasks.")
    pull_parser.add_argument("--updates", required=True, help="JSON file: [{key, status}]")
    args = parser.parse_args()
    root = repo_root(Path(args.root))

    if args.command == "plan":
        print(json.dumps(build_plan(root), indent=2, sort_keys=True))
    elif args.command == "pending":
        count = len(build_plan(root)["plan"])
        print(json.dumps({"pending": count > 0, "count": count}, sort_keys=True))
    elif args.command == "reconcile":
        print(json.dumps(reconcile(root, read_json(Path(args.results), [])), sort_keys=True))
    elif args.command == "apply-pull":
        print(json.dumps(apply_pull(root, read_json(Path(args.updates), [])), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
