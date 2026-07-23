#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import workspace_exists
from quality_tools import cli_main

if __name__ == "__main__":
    # Dormant until the workspace is opted in: this Stop hook only writes
    # completion/coverage reports into .project/.engineering. With no workspace
    # it exits silently (a Stop hook must emit no stdout) and creates nothing.
    if not workspace_exists():
        raise SystemExit(0)
    if "--hook" not in sys.argv:
        sys.argv.append("--hook")
    raise SystemExit(cli_main("stop-completion-check"))
