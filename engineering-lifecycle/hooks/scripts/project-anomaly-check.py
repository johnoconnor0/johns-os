#!/usr/bin/env python3
"""Run the workspace anomaly detector from a hook.

Two modes, matching `hooks/scripts/sync-ledger.py`:

  default   PostToolUse. Relays findings so a workspace problem introduced by an
            edit is visible in the turn that introduced it.
  --stop    Stop. Runs the detector and pushes findings into the surfaced-issues
            queue, but emits NOTHING. Any stdout from a Stop hook is injected back
            into the conversation and re-invokes the model.

Dormant without a workspace, like every other workspace-writing hook here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import workspace_exists  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "project-anomaly-check.py"


def main() -> int:
    if not workspace_exists():
        return 0
    stop_mode = "--stop" in sys.argv
    command = [sys.executable, "-B", str(SCRIPT), "--hook"]
    if stop_mode:
        # On Stop the detector still runs and still queues what it finds - the
        # queue is what the dispatcher acts on. It just does it silently.
        command.append("--emit-queue")
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    if stop_mode:
        return 0
    if proc.stdout.strip():
        sys.stdout.write(proc.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
