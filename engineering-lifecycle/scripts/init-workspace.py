#!/usr/bin/env python3
"""Create the project-local Engineering Lifecycle workspace."""

from __future__ import annotations

import argparse
from pathlib import Path

from eng_common import WORKSPACE, engineering_root, now_iso, repo_root, write_json


DIRS = [
    "profile",
    "lifecycle",
    "initiatives",
    "decisions",
    "handoffs",
    "hygiene",
    "ledger",
    "council",
    "dashboards",
    "reports",
]


def init_workspace(root: Path) -> dict:
    base = engineering_root(root)
    for name in DIRS:
        (base / name).mkdir(parents=True, exist_ok=True)
    manifest = {
        "workspace": str(WORKSPACE).replace("\\", "/"),
        "created_or_checked_at": now_iso(),
        "directories": DIRS,
    }
    write_json(base / "workspace.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to initialize")
    args = parser.parse_args()
    root = repo_root(Path(args.root))
    manifest = init_workspace(root)
    print(f"initialized {manifest['workspace']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
