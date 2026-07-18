#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import workspace_exists
from quality_tools import cli_main

if __name__ == "__main__":
    # Dormant until the workspace is opted in: this hook only writes hygiene
    # reports into .project/.engineering, so with no workspace there is nothing
    # to do and nothing to create.
    if not workspace_exists():
        raise SystemExit(0)
    if "--hook" not in sys.argv:
        sys.argv.append("--hook")
    raise SystemExit(cli_main("post-edit-hygiene"))
