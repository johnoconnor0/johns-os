#!/usr/bin/env python3
"""Apply safe .env.example additions from the hygiene report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import hygiene_report_path, nearest_env_example, read_json_safe, resolve_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually update .env.example")
    args = parser.parse_args()
    # Resolved rather than assumed. This read the report from a hardcoded path
    # under a bare `Path.cwd()`, so running it from anywhere but the repo root
    # found no report and silently reported nothing to add.
    root = resolve_root().root
    cwd = Path.cwd()
    data = read_json_safe(hygiene_report_path(root))
    additions = [
        item["recommended_placeholder"] for item in data.get("new_env_vars", []) if not item.get("in_env_example")
    ]
    if not args.apply:
        print("\n".join(additions) if additions else "no .env.example additions")
        return 0
    # Search upward from the working directory so a monorepo package's own
    # template is honoured, but stop at the resolved root.
    path = nearest_env_example(cwd) or (root / ".env.example")
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
