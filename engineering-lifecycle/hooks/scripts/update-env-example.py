#!/usr/bin/env python3
"""Apply safe .env.example additions from the hygiene report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path.cwd()
REPORT = ROOT / ".project" / ".engineering" / "hygiene" / "hygiene-report.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually update .env.example")
    args = parser.parse_args()
    data = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() and REPORT.stat().st_size else {}
    additions = [item["recommended_placeholder"] for item in data.get("new_env_vars", []) if not item.get("in_env_example")]
    if not args.apply:
        print("\n".join(additions) if additions else "no .env.example additions")
        return 0
    path = ROOT / ".env.example"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    with path.open("a", encoding="utf-8", newline="\n") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        for line in additions:
            key = line.split("=", 1)[0]
            if f"{key}=" not in existing:
                f.write(line + "\n")
    print(f"applied {len(additions)} .env.example addition(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
