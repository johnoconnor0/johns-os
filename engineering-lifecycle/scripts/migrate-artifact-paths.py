#!/usr/bin/env python3
"""Move narrative deliverables out of the machine workspace into .project/docs/engineering.

Two trees, two audiences: `.project/.engineering/` holds runtime state (ledger,
reports, context, council, hygiene, dashboards, questions, registry), and
`.project/docs/engineering/<initiative-id>/` holds the documents a person reads.

An existing workspace has everything in the first tree. This moves the narrative
half across, preserving front matter and git history where git is available, and
leaves the machine half alone.

Dry-run by default. Nothing moves without `--apply`.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from eng_common import docs_root, emit_json, engineering_root, git, relpath, repo_root

# Stage directory -> destination inside docs/engineering/<initiative-id>/.
# Stages absent from this map stay in the workspace: review notes, testing plans
# and release plans are working state, not deliverables anyone reads later.
MOVED_STAGES = {
    "requirements": "",
    "architecture": "",
    "ux": "",
    "design-system": "design-system",
    "implementation": "",
    "data": "data",
    "discovery": "",
    "system-map": "",
    "api": "",
}

# Renames applied on the way across, so the destination names match the skills
# that now produce them.
RENAMES = {
    "architecture-plan.md": "technical-design-document.md",
    "implementation-plan.md": "engineering-plan.md",
    "ux-flow.md": "app-flow.md",
}


def plan_moves(root: Path) -> list[dict[str, str]]:
    initiatives = engineering_root(root) / "initiatives"
    if not initiatives.is_dir():
        return []
    moves: list[dict[str, str]] = []
    for initiative in sorted(path for path in initiatives.iterdir() if path.is_dir()):
        for stage, subdir in MOVED_STAGES.items():
            source_dir = initiative / stage
            if not source_dir.is_dir():
                continue
            for source in sorted(source_dir.rglob("*")):
                if not source.is_file():
                    continue
                relative = source.relative_to(source_dir)
                name = RENAMES.get(relative.name, relative.name)
                target = docs_root(root) / initiative.name
                if subdir:
                    target = target / subdir
                target = target / relative.parent / name
                moves.append({"from": relpath(source, root), "to": relpath(target, root)})
    return moves


def apply_moves(root: Path, moves: list[dict[str, str]], use_git: bool) -> list[str]:
    errors: list[str] = []
    for move in moves:
        source = root / move["from"]
        target = root / move["to"]
        if target.exists():
            errors.append(f"{move['to']}: already exists, skipped")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        moved = False
        if use_git:
            # git mv preserves history for tracked files; untracked ones fall
            # through to a plain move rather than failing the migration.
            code, _out, _err = git(["mv", move["from"], move["to"]], root)
            moved = code == 0
        if not moved:
            try:
                shutil.move(str(source), str(target))
            except OSError as exc:
                errors.append(f"{move['from']}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true", help="Actually move files; otherwise dry-run")
    parser.add_argument("--no-git", action="store_true", help="Use a plain move even inside a git repo")
    args = parser.parse_args()
    root = repo_root(Path(args.root))

    moves = plan_moves(root)
    use_git = not args.no_git and (root / ".git").exists() and shutil.which("git") is not None
    errors: list[str] = []
    if args.apply and moves:
        errors = apply_moves(root, moves, use_git)

    emit_json(
        {
            "root": str(root),
            "docs_root": relpath(docs_root(root), root),
            "move_count": len(moves),
            "moves": moves,
            "applied": bool(args.apply),
            "used_git": use_git if args.apply else None,
            "errors": errors,
            "note": "Dry-run. Re-run with --apply to move." if not args.apply else "Migration applied.",
        }
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
