#!/usr/bin/env python3
"""Validate changed generated artifacts when hooks run after edits."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import CAPTURE_TEXT, engineering_root, repo_root

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate-artifact.py"


def main() -> int:
    # Resolved here rather than at import: resolution reads an environment
    # variable and stats the filesystem, so doing it at module scope binds the
    # answer to whatever cwd the process happened to have when it loaded.
    #
    # Only ever validate the resolved workspace, and stay dormant (no creation)
    # when it does not exist.
    root = repo_root()
    base = engineering_root(root)
    if not base.exists():
        return 0
    artifacts = [str(path) for path in base.rglob("*") if path.suffix.lower() in {".md", ".json"}]
    if not artifacts:
        return 0
    proc = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *artifacts], cwd=root, capture_output=True, check=False, **CAPTURE_TEXT
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
