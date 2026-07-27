#!/usr/bin/env python3
"""Validate changed generated artifacts when hooks run after edits."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import engineering_root, repo_root

ROOT = repo_root()
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate-artifact.py"


def main() -> int:
    # Anchored to the repo root: only ever validate the repo-root workspace, and
    # stay dormant (no creation) when it does not exist.
    base = engineering_root(ROOT)
    if not base.exists():
        return 0
    artifacts = [str(path) for path in base.rglob("*") if path.suffix.lower() in {".md", ".json"}]
    if not artifacts:
        return 0
    proc = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *artifacts], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
