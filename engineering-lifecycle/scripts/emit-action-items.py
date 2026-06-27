#!/usr/bin/env python3
"""Normalize action items into the Engineering Lifecycle ledger format."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from eng_common import engineering_root, now_iso, read_json, repo_root, slugify, write_json


ACTION_RE = re.compile(r"^\s*[-*]\s+\[(?P<state>[ xX])\]\s+(?P<title>.+)$")


def item_from_text(line: str, source: str, index: int) -> dict | None:
    match = ACTION_RE.match(line)
    if not match:
        return None
    title = match.group("title").strip()
    status = "done" if match.group("state").lower() == "x" else "open"
    return {
        "id": f"{slugify(Path(source).stem)}-{index:03d}",
        "title": title,
        "status": status,
        "source": source,
        "created_at": now_iso(),
        "owner": "unassigned",
        "priority": "normal",
    }


def collect_from_markdown(path: Path, root: Path) -> list[dict]:
    rel = str(path.relative_to(root)).replace("\\", "/")
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
                        "source": str(full.relative_to(root)).replace("\\", "/"),
                        "created_at": item.get("created_at") or now_iso(),
                        "owner": item.get("owner", "unassigned"),
                        "priority": item.get("priority", "normal"),
                    }
                    items.append(normalized)
        elif full.suffix.lower() == ".md":
            items.extend(collect_from_markdown(full, root))
    return sorted(items, key=lambda item: (item["source"], item["id"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=".project/.engineering/ledger/action-items.json")
    args = parser.parse_args()
    root = repo_root(Path(args.root))
    items = collect(root, [Path(p) for p in args.inputs])
    payload = {"generated_at": now_iso(), "action_items": items}
    write_json(root / args.out, payload)
    print(f"wrote {len(items)} action item(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
