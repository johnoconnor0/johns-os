#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from quality_tools import cli_main  # noqa: E402

if __name__ == "__main__":
    if "--hook" not in sys.argv:
        sys.argv.append("--hook")
    raise SystemExit(cli_main("capture-question-answers"))
