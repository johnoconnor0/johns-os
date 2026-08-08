#!/usr/bin/env python3
"""Forward to engineering-lifecycle's `eng-life`, wherever it is installed.

`SKILL.md` used to name `${CLAUDE_PLUGIN_ROOT}/../engineering-lifecycle/bin/eng-life`
directly. That path only exists in this repository's own checkout: installed, a plugin
runs from `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, so the `..`
resolved to `cache/<marketplace>/ai-utilities/engineering-lifecycle/bin/eng-life` -
inside ai-utilities, and without the version segment. A shell command cannot pick the
newest of ten installed versions, so the resolution lives here instead of in prose.

Exits 3 when it cannot be found, printing the paths tried. `ai-utilities` is
independently installable and `engineering-lifecycle` genuinely may be absent, so
that is a real outcome rather than an error - but it must say which of the two
happened.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common import resolve_lifecycle_file  # noqa: E402


def main(argv: list[str]) -> int:
    script, tried = resolve_lifecycle_file("bin", "eng-life")
    if script is None:
        print(
            "could not locate eng-life, which ships with engineering-lifecycle. Tried:\n"
            + "\n".join(f"  {path}" for path in tried),
            file=sys.stderr,
        )
        return 3
    completed = subprocess.run(  # noqa: S603 - resolved path, argv list, no shell
        [sys.executable, str(script), *argv],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
