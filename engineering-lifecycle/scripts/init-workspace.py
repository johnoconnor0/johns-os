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
    "questions",
    "dashboards",
    "reports",
    "context",
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
    parser.add_argument("--root", default=".", help="Directory to initialize from (default: current directory)")
    parser.add_argument(
        "--here",
        action="store_true",
        help="Initialize the workspace in --root exactly, without walking up to the git/plugin root. "
        "Use to place .project in a subfolder deliberately (e.g. a nested package).",
    )
    args = parser.parse_args()
    base = Path(args.root).resolve()
    root = base if args.here else repo_root(base)
    manifest = init_workspace(root)
    location = str(root).replace("\\", "/")
    print(f"initialized {manifest['workspace']} at {location}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
