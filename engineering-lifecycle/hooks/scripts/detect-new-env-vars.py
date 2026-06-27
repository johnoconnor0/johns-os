#!/usr/bin/env python3
"""Detect environment variable references and report missing .env.example keys."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
REPORT = ROOT / ".project" / ".engineering" / "hygiene" / "hygiene-report.json"
ENV_RE = re.compile(r"(?:process\.env\.|os\.environ(?:\.get)?\(['\"]|getenv\(['\"])([A-Z][A-Z0-9_]{2,})")
SAFE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".py", ".rb", ".php", ".go", ".rs", ".java", ".cs", ".sh", ".env.example"}


def tracked_files() -> list[Path]:
    return [
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and ".project" not in p.parts
        and "node_modules" not in p.parts
        and p.suffix in SAFE_EXTS
    ]


def env_example_keys() -> set[str]:
    path = ROOT / ".env.example"
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            keys.add(line.split("=", 1)[0].strip())
    return keys


def main() -> int:
    found: dict[str, set[str]] = {}
    for path in tracked_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in ENV_RE.findall(text):
            found.setdefault(name, set()).add(str(path.relative_to(ROOT)).replace("\\", "/"))
    example = env_example_keys()
    missing = [
        {
            "name": name,
            "seen_in": sorted(paths),
            "in_env_example": name in example,
            "recommended_placeholder": f"{name}=<replace-me>",
        }
        for name, paths in sorted(found.items())
        if name not in example
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if REPORT.exists() and REPORT.stat().st_size:
        try:
            data = json.loads(REPORT.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["new_env_vars"] = missing
    data.setdefault("risks", [])
    REPORT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"env var hygiene: {len(missing)} missing .env.example key(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
