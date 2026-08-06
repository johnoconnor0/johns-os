#!/usr/bin/env python3
"""SessionStart context: report workspace availability WITHOUT ever creating it.

The Engineering Lifecycle workspace (`.project/.engineering`) is opt-in per repo.
This hook is detection-only. When the workspace is missing it does not create it —
it asks the assistant to offer `/project-init` via AskUserQuestion, so `.project`
never appears automatically in a repo (or, worse, in whatever subfolder the session
happened to start in). Anchored to the repo root, never `Path.cwd()`.
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import emit_json, engineering_root, hook_additional_context, plugin_root, repo_root, workspace_exists


def provenance() -> str:
    """Where this plugin is actually executing from, and at what version.

    Plugins run from a version-pinned copy under `~/.claude/plugins/cache/...`,
    not from a working tree. Editing the source repo has no effect on a session
    until the plugin is reinstalled. Surfacing the resolved root and version in
    the first line of every session makes that drift obvious immediately rather
    than after an hour of edits that appear to do nothing.
    """
    base = plugin_root()
    version = "unknown"
    manifest = base / ".claude-plugin" / "plugin.json"
    with contextlib.suppress(OSError, ValueError):
        version = json.loads(manifest.read_text(encoding="utf-8")).get("version", "unknown")
    display = str(base).replace("\\", "/")
    note = ""
    if ".claude/plugins/cache" in display:
        note = " (installed copy; edits to the source checkout require a reinstall to take effect)"
    return f"engineering-lifecycle v{version} running from {display}{note}."


def _surfacing_directive(root: Path) -> str:
    """A short standing instruction, only when issue filing is switched on.

    Gated on enablement so a project that has not configured a tracker stays quiet,
    and kept to three lines because a long standing directive costs tokens in every
    session and gets skimmed in all of them.
    """
    try:
        from tracker import load_settings

        settings = load_settings(root)
    except Exception:
        return ""
    if not settings.get("enabled"):
        return ""
    return (
        "\n\nIssue filing is on for this project "
        f"(provider: {settings.get('provider')}). When you notice something in this "
        "project that is wrong, contradictory, silently failing or degraded, record "
        'it: `python "${CLAUDE_PLUGIN_ROOT}/scripts/surface-issue.py" record --title "..."`. '
        "See references/issue-surfacing-policy.md for what counts."
    )


def main() -> int:
    root = repo_root()
    workspace = engineering_root(root)
    display_root = str(root).replace("\\", "/")
    display_ws = str(workspace).replace("\\", "/")

    if workspace_exists(root):
        message = (
            f"{provenance()}\n"
            f"Engineering Lifecycle workspace detected at {display_ws}. "
            "Lifecycle hooks and skills are active for this repo; proceed."
            f"{_surfacing_directive(root)}"
        )
    else:
        message = (
            f"{provenance()}\n"
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
