#!/usr/bin/env python3
"""Run the deterministic public-repository validation suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dirs() -> list[str]:
    """Every Python test suite in the repository, found rather than listed.

    This used to name `tests` and `engineering-lifecycle/tests` explicitly, which
    meant `ai-utilities` - the plugin with the broadest tool permissions in the
    marketplace - could add a test suite and CI would never run it. A hardcoded
    list of the things to check is the same defect the reference checker and the
    audit rebuild both exist to fix; it does not deserve to survive here either.
    """
    found = ["tests"] if (ROOT / "tests").is_dir() else []
    for candidate in sorted(ROOT.glob("*/tests")):
        if candidate.is_dir() and any(candidate.rglob("test_*.py")):
            found.append(candidate.relative_to(ROOT).as_posix())
    return found


def commands() -> list[list[str]]:
    suites = [[sys.executable, "-m", "unittest", "discover", "-s", directory] for directory in test_dirs()]
    return [
        [sys.executable, str(ROOT / "scripts" / "johns-os-marketplace.py"), "validate"],
        [sys.executable, str(ROOT / "scripts" / "check-cli-version.py")],
        [sys.executable, str(ROOT / "engineering-lifecycle" / "bin" / "eng-life"), "validate"],
        # Documentation naming a plugin, skill, agent, command or marketplace that
        # does not exist fails the build. Path references are reported but advisory.
        [sys.executable, "-B", str(ROOT / "engineering-lifecycle" / "scripts" / "reference-check.py"), "--root", "."],
        *suites,
        # The e2e fixture and node_modules are generated; compiling them is noise.
        [sys.executable, "-m", "compileall", "-q", "-x", r"(node_modules|\.fixture)", "."],
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
