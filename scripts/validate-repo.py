#!/usr/bin/env python3
"""Run the deterministic public-repository validation suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commands() -> list[list[str]]:
    return [
        [sys.executable, str(ROOT / "scripts" / "johns-os-marketplace.py"), "validate"],
        [sys.executable, str(ROOT / "engineering-lifecycle" / "bin" / "eng-life"), "validate"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        [sys.executable, "-m", "unittest", "discover", "-s", "engineering-lifecycle/tests"],
        [sys.executable, "-m", "compileall", "-q", "."],
    ]


def main() -> int:
    for command in commands():
        print(f"$ {' '.join(command)}")
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    print("repository validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
