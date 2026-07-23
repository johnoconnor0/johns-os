#!/usr/bin/env python3
"""Collect factual repository profile data without inferring product intent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eng_common import git, git_files, repo_root, write_json

MANIFEST_NAMES = {
    "package.json",
    "pnpm-workspace.yaml",
    "yarn.lock",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "Gemfile",
    "Dockerfile",
    "docker-compose.yml",
    "compose.yaml",
}


def classify(paths: list[Path]) -> dict:
    suffixes: dict[str, int] = {}
    manifests: list[str] = []
    docs: list[str] = []
    tests: list[str] = []
    configs: list[str] = []
    for path in paths:
        text = str(path).replace("\\", "/")
        suffixes[path.suffix or "<none>"] = suffixes.get(path.suffix or "<none>", 0) + 1
        if path.name in MANIFEST_NAMES:
            manifests.append(text)
        if path.suffix.lower() in {".md", ".mdx", ".rst"}:
            docs.append(text)
        if any(part.lower() in {"test", "tests", "__tests__", "spec", "specs"} for part in path.parts):
            tests.append(text)
        if path.name.startswith(".") or path.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".ini"}:
            configs.append(text)
    return {
        "file_count": len(paths),
        "suffix_counts": dict(sorted(suffixes.items())),
        "manifests": sorted(manifests),
        "docs": sorted(docs),
        "tests": sorted(tests),
        "configs": sorted(configs),
    }


def build_profile(root: Path) -> dict:
    paths = git_files(root)
    code, branch, _ = git(["branch", "--show-current"], root)
    status_code, status, _ = git(["status", "--porcelain"], root)
    return {
        "repo_root": str(root),
        "git": {
            "available": code == 0,
            "branch": branch.strip() if code == 0 else None,
            "dirty": bool(status.strip()) if status_code == 0 else None,
        },
        "facts": classify(paths),
        "unknowns": [
            "Product goals, target users, and runtime ownership must come from docs or user input.",
            "Secrets and local-only values are intentionally not inspected.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=".project/.engineering/profile/repo-profile.json")
    parser.add_argument("--print", action="store_true", dest="print_stdout")
    args = parser.parse_args()
    root = repo_root(Path(args.root))
    profile = build_profile(root)
    write_json(root / args.out, profile)
    if args.print_stdout:
        print(json.dumps(profile, indent=2, sort_keys=True))
    else:
        print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
