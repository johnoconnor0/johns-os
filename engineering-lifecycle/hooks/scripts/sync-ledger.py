#!/usr/bin/env python3
"""Hook wrapper for ledger synchronization.

Two modes:

- Default (PostToolUse on Edit/MultiEdit/Write): sync and relay output.
- `--stop` (Stop hook): catch artifacts written by Bash, `python`, or any other
  path that never triggers PostToolUse. Debounced against the ledger's own mtime
  so a turn that changed nothing does no work, and **always silent** — Stop-hook
  stdout is re-injected into the conversation and causes an endless standby loop
  (see hygiene-stop-check.py for the same lesson).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import engineering_root, repo_root, workspace_exists

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sync-ledger.py"

# Directories the ledger itself writes. Their mtimes are an effect of syncing,
# never a reason to sync, so excluding them keeps the check from self-triggering.
_DERIVED = {"ledger", "dashboards"}


def workspace_is_dirty(root: Path) -> bool:
    """True when any source artifact is newer than the last ledger sync."""
    base = engineering_root(root)
    ledger = base / "ledger" / "ledger.json"
    if not ledger.exists():
        return True
    synced_at = ledger.stat().st_mtime
    for child in base.iterdir():
        if child.name in _DERIVED:
            continue
        if child.is_file():
            if child.stat().st_mtime > synced_at:
                return True
            continue
        for path in child.rglob("*"):
            if path.is_file() and path.stat().st_mtime > synced_at:
                return True
    return False


def main() -> int:
    stop_mode = "--stop" in sys.argv[1:]

    # Dormant until the workspace is opted in. The explicit CLI path
    # (`eng-life sync-ledger`) invokes scripts/sync-ledger.py directly and still
    # creates the workspace on demand; this automatic wrapper must not.
    if not workspace_exists():
        return 0
    if stop_mode and not workspace_is_dirty(repo_root()):
        return 0

    proc = subprocess.run([sys.executable, "-B", str(SCRIPT)], text=True, capture_output=True, check=False)
    if stop_mode:
        # Silent on *stdout* - that is the rule, and the reason is the standby loop
        # in the docstring above. It was never a reason to discard stderr as well,
        # which is what left a crash in the ledger sync with no traceback anywhere:
        # the wrapper returned the child's exit code and threw away the only thing
        # that said why. stderr is not re-injected as context, so it is safe to
        # relay, and the child's stdout follows it only when the run failed, where
        # it is diagnostic rather than conversational.
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        if proc.returncode != 0 and proc.stdout.strip():
            print(proc.stdout.strip(), file=sys.stderr)
        return proc.returncode
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
