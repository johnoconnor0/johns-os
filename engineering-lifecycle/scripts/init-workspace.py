#!/usr/bin/env python3
"""Create the project-local Engineering Lifecycle workspace."""

from __future__ import annotations

import argparse
from pathlib import Path

from eng_common import WORKSPACE, engineering_root, now_iso, resolve_root, write_json

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
    "tracker",
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
    parser.add_argument("--root", default=None, help="Directory to initialize in, exactly. No walking up.")
    parser.add_argument(
        "--here",
        action="store_true",
        help="Initialize the workspace in the current directory exactly, without resolving. "
        "Use to place .project in a subfolder deliberately (e.g. a nested package).",
    )
    args = parser.parse_args()
    # Creation and resolution go through the same function, which is the whole
    # point. They used to disagree: `--here` was the only code path in the plugin
    # that skipped the walk, so it could create a workspace that nothing which
    # later read the tree could address. `resolve_root` now knows about the
    # workspace marker, so a deliberately nested workspace is findable afterwards.
    if args.root:
        root = resolve_root(explicit=Path(args.root)).root
    elif args.here:
        root = Path.cwd().resolve()
    else:
        root = resolve_root().root
    manifest = init_workspace(root)
    location = str(root).replace("\\", "/")
    print(f"initialized {manifest['workspace']} at {location}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
