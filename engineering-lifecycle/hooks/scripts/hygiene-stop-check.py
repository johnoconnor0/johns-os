#!/usr/bin/env python3
"""Stop hook hygiene reminder."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path.cwd()
REPORT = ROOT / ".project" / ".engineering" / "hygiene" / "hygiene-report.json"


def main() -> int:
    if not REPORT.exists() or REPORT.stat().st_size == 0:
        print("engineering lifecycle: no hygiene report found")
        return 0
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    missing_env = len(data.get("new_env_vars", []))
    ignores = len(data.get("gitignore_candidates", []))
    if missing_env or ignores:
        print(f"engineering lifecycle hygiene: {missing_env} env var(s), {ignores} gitignore candidate(s) need review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
