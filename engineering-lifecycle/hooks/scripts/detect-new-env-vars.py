#!/usr/bin/env python3
"""Detect environment variable references and report missing .env.example keys."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import engineering_root, env_example_keys, repo_root, workspace_exists

# Scan the working directory (so a monorepo package's own .env.example is honored
# by the ancestor-walk), but write the report into the repo-root workspace so
# .project only ever lives at the repo root — never in whatever subfolder a hook
# happened to fire from.
CWD = Path.cwd()
ROOT = repo_root(CWD)
REPORT = engineering_root(ROOT) / "hygiene" / "hygiene-report.json"
ENV_RE = re.compile(r"(?:process\.env\.|os\.environ(?:\.get)?\(['\"]|getenv\(['\"])([A-Z][A-Z0-9_]{2,})")
SAFE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".py", ".rb", ".php", ".go", ".rs", ".java", ".cs", ".sh", ".env.example"}


def tracked_files() -> list[Path]:
    return [
        p
        for p in CWD.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and ".project" not in p.parts
        and "node_modules" not in p.parts
        and p.suffix in SAFE_EXTS
    ]


def main() -> int:
    # Dormant until the workspace is opted in. `--ensure-workspace` (passed by the
    # explicit `eng-hygiene detect` CLI) creates it on demand; the automatic
    # PostToolUse hook passes nothing and stays dormant.
    if not workspace_exists(ROOT) and "--ensure-workspace" not in sys.argv:
        return 0
    found: dict[str, set[str]] = {}
    for path in tracked_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in ENV_RE.findall(text):
            found.setdefault(name, set()).add(str(path.relative_to(CWD)).replace("\\", "/"))
    example = env_example_keys(CWD)
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
    # Full inventory of every referenced variable with an accurate in_env_example flag —
    # documented variables show true here even though they are excluded from new_env_vars.
    inventory = [
        {"name": name, "seen_in": sorted(paths), "in_env_example": name in example}
        for name, paths in sorted(found.items())
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if REPORT.exists() and REPORT.stat().st_size:
        try:
            data = json.loads(REPORT.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["new_env_vars"] = missing
    data["env_var_inventory"] = inventory
    data.setdefault("risks", [])
    REPORT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"env var hygiene: {len(missing)} missing .env.example key(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
