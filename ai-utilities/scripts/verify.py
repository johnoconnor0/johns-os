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

## Whose command is it

Running the project's own checks is the point of this script, so "it executes repo
code" is the feature, not the bug. The line that matters is narrower: rung 2 above
can be filled from `.project/.engineering/context/stack.json` *inside the repository
being audited*, and that is a verbatim string a repository chose. An inert-looking
JSON file selecting the command is not the same as `make check` being present, so
those commands are gated behind `--allow-untrusted-commands` and reported as
`unverified` by default.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from audit_common import command_argv as _argv
from audit_common import repo_root
from audit_common import scrub_secrets as _scrub
from stack_probe import resolve_stack

# Default wall-clock budget per command. There used to be none at all, so a repo
# that declared a command which blocks forever hung the audit forever.
DEFAULT_TIMEOUT = 900

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
        return {"source": "entrypoint", "trusted": True, "reason": reason, "commands": [command]}

    stack = resolve_stack(root, prefer)
    declared = [stack["test_commands"][key] for key in _COMMAND_ORDER if stack["test_commands"].get(key)]
    if declared:
        # The `workspace` rung reads the audited repo's own stack.json, so its
        # strings were chosen by that repository. Every other rung derives its
        # commands here, from file presence.
        from_repo = stack["detector"] == "workspace"
        return {
            "source": "declared",
            "detector": stack["detector"],
            "trusted": not from_repo,
            "reason": f"stack.test_commands, resolved by the {stack['detector']} detector",
            "commands": declared,
        }

    for marker, commands in _FALLBACKS:
        if (root / marker).is_file():
            runnable = [command for command in commands if shutil.which(command.split()[0])]
            if runnable:
                return {"source": "fallback", "trusted": True, "reason": f"{marker} present", "commands": runnable}

    return {
        "source": "none",
        "trusted": True,
        "reason": "this project declares no verification command and none could be detected",
        "commands": [],
    }


def verify(
    root: Path,
    prefer: str = "",
    dry_run: bool = False,
    allow_untrusted: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
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

    if not chosen.get("trusted", True) and not allow_untrusted:
        return {
            **chosen,
            "verified": None,
            "status": "unverified",
            "results": [],
            "reason": (
                f"{chosen['reason']}; those strings come from the audited repository's own "
                "stack.json. Re-run with --allow-untrusted-commands to execute them."
            ),
        }

    results = []
    for command in chosen["commands"]:
        argv = _argv(command)
        if argv is None:
            results.append(
                {
                    "cmd": command,
                    "exit": None,
                    "status": "skipped",
                    "output": "",
                    "reason": "needs a shell, or its executable is not on PATH",
                }
            )
            continue
        try:
            proc = subprocess.run(  # noqa: S603 - argv list, no shell, resolved executable
                argv, cwd=root, text=True, capture_output=True, check=False, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            results.append({"cmd": command, "exit": None, "status": "timeout", "output": ""})
            continue
        except OSError as exc:
            results.append({"cmd": command, "exit": None, "status": "error", "output": str(exc)})
            continue
        output = _scrub(((proc.stdout or "") + (proc.stderr or ""))[-4000:])
        results.append({"cmd": command, "exit": proc.returncode, "status": "ran", "output": output})

    failed = [item for item in results if item.get("status") == "ran" and item["exit"] != 0]
    inconclusive = [item for item in results if item.get("status") in {"timeout", "error"}]
    ran = [item for item in results if item.get("status") == "ran"]
    if failed:
        status = "failed"
    elif not ran:
        # Every command was skipped, timed out or failed to start. Reporting that
        # as "passed" is the exact dishonesty this module's docstring forbids.
        status = "unverified"
    else:
        status = "passed"
    return {
        **chosen,
        "verified": bool(ran) and not failed and not inconclusive,
        "status": status,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--prefer", default="", choices=["", "workspace", "imported", "vendored"])
    parser.add_argument("--dry-run", action="store_true", help="Report which commands would run, and why")
    parser.add_argument(
        "--allow-untrusted-commands",
        action="store_true",
        help="Run commands taken verbatim from the audited repository's own stack.json",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Seconds per command")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root not in ("", ".") else repo_root(Path("."))
    result = verify(root, args.prefer, args.dry_run, args.allow_untrusted_commands, args.timeout)
    print(json.dumps(result, indent=2, sort_keys=True))
    # Non-zero on a real failure only. "unverified" is not a failure, it is an
    # absence, and the caller has to decide what to do about it.
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
