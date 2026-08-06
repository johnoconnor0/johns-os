#!/usr/bin/env python3
"""Run whatever this repository uses to verify itself.

Replaces `verify-stack.sh`, and not by translating it. That script re-derived
verifier commands from file presence, which is how it came to probe for
`scripts/check-versions.mjs` and `tests/scripts/test_smoke.py` - two files that
belong to a different repository and have never existed in this one. It also missed
`python scripts/validate-repo.py`, which is this repository's actual single
entrypoint for validation.

The correct implementation is to *ask*, in descending order of authority:

1. A repository-wide validation entrypoint, if the project has one. When a project
   exposes one command that runs everything, that command is the verifier and no
   detection is needed or wanted.
2. `stack.test_commands`, resolved by the stack ladder. That map exists precisely so
   only commands the project really declares are emitted.
3. File-presence detection, as a last resort.

And when none of those produce anything, say so. A verifier that finds nothing must
report "unverified", never "passed" - the same rule the audit's five outcomes exist
to enforce.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from audit_common import repo_root
from stack_probe import resolve_stack

# A single command that runs everything, in the order we would trust them.
_ENTRYPOINTS = (
    ("scripts/validate-repo.py", "python scripts/validate-repo.py"),
    ("Makefile", "make check"),
    ("Taskfile.yml", "task check"),
    ("justfile", "just check"),
)

# Last resort only: reached when the project declares nothing.
_FALLBACKS = (
    ("Cargo.toml", ("cargo check", "cargo test")),
    ("go.mod", ("go vet ./...", "go test ./...")),
    ("pyproject.toml", ("python -m ruff check .",)),
)

_COMMAND_ORDER = ("typecheck", "lint", "unit", "build")


def _entrypoint(root: Path) -> tuple[str, str] | None:
    for marker, command in _ENTRYPOINTS:
        if not (root / marker).is_file():
            continue
        if marker == "Makefile" and "check:" not in (root / marker).read_text(encoding="utf-8", errors="ignore"):
            continue
        return command, f"{marker} is this repository's validation entrypoint"
    return None


def plan(root: Path, prefer: str = "") -> dict[str, Any]:
    """The commands that would run, and why - without running them."""
    found = _entrypoint(root)
    if found:
        command, reason = found
        return {"source": "entrypoint", "reason": reason, "commands": [command]}

    stack = resolve_stack(root, prefer)
    declared = [stack["test_commands"][key] for key in _COMMAND_ORDER if stack["test_commands"].get(key)]
    if declared:
        return {
            "source": "declared",
            "reason": f"stack.test_commands, resolved by the {stack['detector']} detector",
            "commands": declared,
        }

    for marker, commands in _FALLBACKS:
        if (root / marker).is_file():
            runnable = [command for command in commands if shutil.which(command.split()[0])]
            if runnable:
                return {"source": "fallback", "reason": f"{marker} present", "commands": runnable}

    return {
        "source": "none",
        "reason": "this project declares no verification command and none could be detected",
        "commands": [],
    }


def verify(root: Path, prefer: str = "", dry_run: bool = False) -> dict[str, Any]:
    chosen = plan(root, prefer)
    if dry_run or not chosen["commands"]:
        return {
            **chosen,
            "verified": False if not chosen["commands"] else None,
            "results": [],
            # The honest answer when nothing ran. `verify-stack.sh` exited 0 here,
            # which reads as a pass to anything checking the exit code.
            "status": "unverified" if not chosen["commands"] else "not-run",
        }

    results = []
    for command in chosen["commands"]:
        proc = subprocess.run(command, cwd=root, shell=True, text=True, capture_output=True, check=False)
        output = ((proc.stdout or "") + (proc.stderr or ""))[-4000:]
        results.append({"cmd": command, "exit": proc.returncode, "output": output})
    failed = [item for item in results if item["exit"] != 0]
    return {
        **chosen,
        "verified": not failed,
        "status": "failed" if failed else "passed",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--prefer", default="", choices=["", "workspace", "imported", "vendored"])
    parser.add_argument("--dry-run", action="store_true", help="Report which commands would run, and why")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root not in ("", ".") else repo_root(Path("."))
    result = verify(root, args.prefer, args.dry_run)
    print(json.dumps(result, indent=2, sort_keys=True))
    # Non-zero on a real failure only. "unverified" is not a failure, it is an
    # absence, and the caller has to decide what to do about it.
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
