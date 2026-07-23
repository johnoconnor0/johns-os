#!/usr/bin/env python3
"""SessionStart context: report workspace availability WITHOUT ever creating it.

The Engineering Lifecycle workspace (`.project/.engineering`) is opt-in per repo.
This hook is detection-only. When the workspace is missing it does not create it —
it asks the assistant to offer `/project-init` via AskUserQuestion, so `.project`
never appears automatically in a repo (or, worse, in whatever subfolder the session
happened to start in). Anchored to the repo root, never `Path.cwd()`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import emit_json, engineering_root, hook_additional_context, repo_root, workspace_exists


def main() -> int:
    root = repo_root()
    workspace = engineering_root(root)
    display_root = str(root).replace("\\", "/")
    display_ws = str(workspace).replace("\\", "/")

    if workspace_exists(root):
        message = (
            f"Engineering Lifecycle workspace detected at {display_ws}. "
            "Lifecycle hooks and skills are active for this repo; proceed."
        )
    else:
        message = (
            f"No Engineering Lifecycle workspace exists at the repo root ({display_root}). "
            "The plugin is dormant here and will NOT create `.project` automatically.\n\n"
            "Before starting lifecycle work this session, use AskUserQuestion to ask whether to "
            "initialize it:\n"
            '  - Question: "Initialize the Engineering Lifecycle workspace (.project/.engineering) '
            'at the repo root for this project?"\n'
            '  - Options: "Initialize now" (run the /project-init command) and "Not now" '
            "(stay dormant this session).\n\n"
            "Rules:\n"
            "  - Never create `.project` unless the user chooses to initialize.\n"
            "  - `.project` belongs at the repo root only. To place it in a subfolder deliberately, "
            "the user runs `/project-init here` from that subfolder.\n"
            "  - If the user declines, proceed with their request without the workspace and do not "
            "ask again this session."
        )

    emit_json(hook_additional_context("SessionStart", message))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
