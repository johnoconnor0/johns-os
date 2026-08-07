#!/usr/bin/env python3
"""Normalize action items into the Engineering Lifecycle ledger format."""

from __future__ import annotations

import argparse
from pathlib import Path

from eng_common import (  # noqa: F401  (ACTION_RE re-exported for existing callers)
    ACTION_RE,
    WORKSPACE,
    item_from_text,
    now_iso,
    read_json,
    relpath,
    resolve_cli_root,
    slugify,
    write_json,
)


def collect_from_markdown(path: Path, root: Path) -> list[dict]:
    rel = relpath(path, root)
    items: list[dict] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        item = item_from_text(line, rel, index)
        if item:
            items.append(item)
    return items


def collect(root: Path, inputs: list[Path]) -> list[dict]:
    items: list[dict] = []
    for path in inputs:
        full = path if path.is_absolute() else root / path
        if full.suffix.lower() == ".json":
            data = read_json(full, {})
            raw_items = data if isinstance(data, list) else data.get("action_items", [])
            for index, item in enumerate(raw_items, 1):
                if isinstance(item, dict):
                    normalized = {
                        "id": item.get("id") or f"{slugify(full.stem)}-{index:03d}",
                        "title": item.get("title") or item.get("description") or "Untitled action item",
                        "status": item.get("status", "open"),
                        "source": relpath(full, root),
                        "created_at": item.get("created_at") or now_iso(),
                        "owner": item.get("owner", "unassigned"),
                        "priority": item.get("priority", "normal"),
                    }
                    items.append(normalized)
        elif full.suffix.lower() == ".md":
            items.extend(collect_from_markdown(full, root))
    return sorted(items, key=lambda item: (item["source"], item["id"]))


# Fields written back by something other than this script, which must therefore
# survive a re-emit. `linear-sync.py reconcile` writes the first two after an issue
# is created; a human or a pull sets the status.
_PRESERVED = ("linear_id", "linear_url", "external", "owner", "priority")


def merge_with_existing(path: Path, items: list[dict]) -> list[dict]:
    """Re-emitted items, keeping what only the tracker round trip knows.

    This function used to not exist: `main` wrote the freshly parsed list straight
    over the file. Every `linear_id` and `linear_url` that `linear-sync.py reconcile`
    had written back was destroyed on the next plan edit, so the following `plan`
    saw the task as untracked and created a second issue for it.
    """
    previous = read_json(path, {})
    known = {
        item.get("id"): item
        for item in (previous.get("action_items", []) if isinstance(previous, dict) else [])
        if isinstance(item, dict) and item.get("id")
    }
    for item in items:
        prior = known.get(item["id"])
        if not prior:
            continue
        for field in _PRESERVED:
            if prior.get(field) is not None and item.get(field) in (None, "", "unassigned", "normal"):
                item[field] = prior[field]
        # A status advanced elsewhere - closed in the tracker, or marked in-progress
        # by hand - outranks the checkbox state re-parsed from the plan, unless the
        # plan itself now says done.
        if prior.get("status") not in (None, "open") and item.get("status") == "open":
            item["status"] = prior["status"]
        item["created_at"] = prior.get("created_at", item["created_at"])
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--root", default=None)
    parser.add_argument("--out", default=str(WORKSPACE / "ledger" / "action-items.json").replace("\\", "/"))
    args = parser.parse_args()
    root = resolve_cli_root(args.root).root
    out = root / args.out
    items = merge_with_existing(out, collect(root, [Path(p) for p in args.inputs]))
    payload = {"generated_at": now_iso(), "action_items": items}
    write_json(out, payload)
    print(f"wrote {len(items)} action item(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
