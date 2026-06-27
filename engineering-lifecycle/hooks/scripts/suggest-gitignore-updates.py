#!/usr/bin/env python3
"""Suggest safe .gitignore additions for generated or local-only files."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path.cwd()
REPORT = ROOT / ".project" / ".engineering" / "hygiene" / "hygiene-report.json"
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
    path = ROOT / ".gitignore"
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()}


def untracked() -> list[str]:
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return []
    return [line[3:] for line in proc.stdout.splitlines() if line.startswith("?? ")]


def main() -> int:
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
