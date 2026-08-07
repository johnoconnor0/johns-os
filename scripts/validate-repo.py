#!/usr/bin/env python3
"""Run the deterministic public-repository validation suite."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def node_suite() -> list[list[str]]:
    """The CLI's own tests, if a Node runtime is available.

    The CLI is the only code every external user runs and the only thing here
    that is not Python, so this is the one place the suite needs an interpreter
    it cannot assume. `node --test` is built in, so there is nothing to install,
    but Node itself may genuinely be absent on a Python contributor's machine.

    Skipping is therefore correct. Skipping *silently* is not: this repository
    published a broken package because a check that never ran looked exactly
    like a check that passed, so an absent runtime says so out loud.

    The files are enumerated rather than handed a directory on purpose.
    `node --test <dir>` reports `pass 0` and a single failing pseudo-test on
    some versions - it neither runs the tests nor obviously fails - while
    `node --test <file>` is stable across the supported range. Given the bug
    above, a runner whose success is indistinguishable from doing nothing is
    not one to leave in place.
    """
    files = sorted((ROOT / "cli" / "test").glob("*.test.js"))
    if not files:
        return []
    node = shutil.which("node")
    if not node:
        print("! skipping the CLI test suite: `node` is not on PATH.")
        print("  The Python suites still run. CI always runs the CLI tests;")
        print("  install Node >= 20.11.0 to run them here.")
        return []
    # Absolute paths: everything runs with cwd=ROOT, and each test file's own
    # imports resolve relative to itself.
    return [[node, "--test", *(str(f) for f in files)]]


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
        *node_suite(),
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
