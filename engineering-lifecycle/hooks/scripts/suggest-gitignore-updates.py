#!/usr/bin/env python3
"""Suggest safe .gitignore additions for generated or local-only files."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import engineering_root, repo_root, workspace_exists

# Inspect the working directory's .gitignore / untracked files, but write the
# report into the repo-root workspace so .project stays at the repo root.
CWD = Path.cwd()
ROOT = repo_root(CWD)
REPORT = engineering_root(ROOT) / "hygiene" / "hygiene-report.json"
SAFE_PATTERNS = [
    (".turbo/", "Generated Turborepo cache"),
    (".next/", "Generated Next.js build output"),
    ("dist/", "Generated distribution output"),
    ("build/", "Generated build output"),
    ("coverage/", "Generated test coverage"),
    ("*.log", "Local log file"),
    ("*.sqlite", "Local database file"),
    ("*.db", "Local database file"),
]
UNSAFE = {"src/", "app/", "lib/", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}


def gitignore_lines() -> set[str]:
    path = CWD / ".gitignore"
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()}


def untracked() -> list[str]:
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=CWD, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return []
    return [line[3:] for line in proc.stdout.splitlines() if line.startswith("?? ")]


def main() -> int:
    # Dormant until the workspace is opted in. `--ensure-workspace` (passed by the
    # explicit `eng-hygiene detect` CLI) creates it on demand; the automatic
    # PostToolUse hook passes nothing and stays dormant.
    if not workspace_exists(ROOT) and "--ensure-workspace" not in sys.argv:
        return 0
    existing = gitignore_lines()
    candidates = []
    names = untracked()
    for pattern, reason in SAFE_PATTERNS:
        if pattern in existing or pattern in UNSAFE:
            continue
        matched = any(
            item.startswith(pattern.rstrip("/")) if pattern.endswith("/") else item.endswith(pattern.lstrip("*"))
            for item in names
        )
        if matched:
            candidates.append({"pattern": pattern, "reason": reason, "safe_to_add": True})
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if REPORT.exists() and REPORT.stat().st_size:
        try:
            data = json.loads(REPORT.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["gitignore_candidates"] = candidates
    REPORT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"gitignore hygiene: {len(candidates)} safe candidate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
