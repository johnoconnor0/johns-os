#!/usr/bin/env python3
"""Detect environment variable references and report missing .env.example keys."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import (
    builds_env_names_dynamically,
    classify_file_path,
    configured_env_accessors,
    env_example_keys,
    env_names_in,
    git,
    repo_root,
    workspace_exists,
    write_hygiene_part,
)

# Scan the working directory (so a monorepo package's own .env.example is honored
# by the ancestor-walk), but write the report into the repo-root workspace so
# .project only ever lives at the repo root — never in whatever subfolder a hook
# happened to fire from.
CWD = Path.cwd()
ROOT = repo_root(CWD)
# Detection lives in eng_common.env_names_in. This script used to keep its own
# private regex, which is how it and env_example_sync came to disagree about the
# same repository — a difference nobody could see without running both.
SAFE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".py", ".rb", ".php", ".go", ".rs", ".java", ".cs", ".sh", ".env.example"}


def scannable(path: Path) -> bool:
    # Source and config only, the same classes `env_example_sync` scans. Test files
    # are full of env-var-shaped fixtures that document nothing and configure
    # nothing; counting them made this tool's totals disagree with the sync report
    # even when both resolved every name identically.
    if not (
        path.is_file()
        and ".git" not in path.parts
        and ".project" not in path.parts
        and "node_modules" not in path.parts
        and path.suffix in SAFE_EXTS
    ):
        return False
    try:
        # Classify the repo-relative path. Handing it an absolute one would let a
        # directory name anywhere above the checkout decide the classification.
        relative = path.relative_to(CWD)
    except ValueError:
        relative = path
    return classify_file_path(relative) in {"source", "config"}


def tracked_files() -> list[Path]:
    """Files under CWD that git considers part of the repository.

    `--cached --others --exclude-standard` is tracked plus untracked-but-not-ignored,
    so a fresh checkout or a module written moments ago stays in scope while ignored
    trees drop out. An unfiltered walk reported eleven undocumented variables from a
    shelved, gitignored plugin — findings against code the repository does not ship,
    and the reason this tool's totals diverged from `env_example_sync`, which has
    always gone through git. Paths print relative to the working directory, which is
    the base CWD already assumes. Falls back to a plain walk outside a repo.
    """
    code, out, _ = git(["ls-files", "--cached", "--others", "--exclude-standard"], CWD)
    candidates = [CWD / line for line in out.splitlines() if line.strip()] if code == 0 else list(CWD.rglob("*"))
    return [path for path in candidates if scannable(path)]


def main() -> int:
    # Dormant until the workspace is opted in. `--ensure-workspace` (passed by the
    # explicit `eng-hygiene detect` CLI) creates it on demand; the automatic
    # PostToolUse hook passes nothing and stays dormant.
    if not workspace_exists(ROOT) and "--ensure-workspace" not in sys.argv:
        return 0
    found: dict[str, set[Path]] = {}
    dynamic: set[str] = set()
    accessors = configured_env_accessors(ROOT)
    for path in tracked_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in env_names_in(path, text, accessors):
            found.setdefault(name, set()).add(path)
        if builds_env_names_dynamically(text):
            dynamic.add(str(path.relative_to(CWD)).replace("\\", "/"))

    # Resolve templates per REFERENCING FILE, not once from the working directory.
    # The ancestor walk only goes up, so starting it at the repo root of a monorepo
    # can only ever find a root-level template and would report every package-level
    # variable as undocumented forever. Each reference is still checked only against
    # templates above itself, so one package's .env.example can never mask another's
    # genuinely undocumented variable.
    keys_by_dir: dict[Path, frozenset[str]] = {}

    def documented(name: str, paths: set[Path]) -> bool:
        for path in paths:
            directory = path.parent.resolve()
            if directory not in keys_by_dir:
                keys_by_dir[directory] = frozenset(env_example_keys(directory, ROOT))
            if name in keys_by_dir[directory]:
                return True
        return False

    def rels(paths: set[Path]) -> list[str]:
        return sorted(str(p.relative_to(CWD)).replace("\\", "/") for p in paths)

    missing = [
        {
            "name": name,
            "seen_in": rels(paths),
            "in_env_example": False,
            "recommended_placeholder": f"{name}=<replace-me>",
        }
        for name, paths in sorted(found.items())
        if not documented(name, paths)
    ]
    # Full inventory of every referenced variable with an accurate in_env_example flag —
    # documented variables show true here even though they are excluded from new_env_vars.
    inventory = [
        {"name": name, "seen_in": rels(paths), "in_env_example": documented(name, paths)}
        for name, paths in sorted(found.items())
    ]
    write_hygiene_part(
        ROOT,
        "env-vars",
        {
            "new_env_vars": missing,
            "env_var_inventory": inventory,
            # Where the detector knows it cannot see: names assembled at runtime
            # cannot be enumerated statically. Kept out of new_env_vars so it never
            # inflates the actionable list, but recorded so "no missing keys" is
            # not read as "no undocumented variables" for a file that builds its
            # names dynamically.
            "dynamic_env_access": sorted(dynamic),
        },
    )
    print(f"env var hygiene: {len(missing)} missing .env.example key(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
