#!/usr/bin/env python3
"""Capture a small stop-hook event for lifecycle observability."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eng_common import engineering_root, repo_root, workspace_exists

ROOT = repo_root()
LOG = engineering_root(ROOT) / "reports" / "session-events.jsonl"


def main() -> int:
    # Dormant until the workspace is opted in: never create .project just to log
    # a session-stop event. Anchored to the repo root so a Stop firing from a
    # subfolder cannot drop a stray .project there.
    if not workspace_exists(ROOT):
        return 0
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {"at": datetime.now(UTC).replace(microsecond=0).isoformat(), "event": "session_stop"}
    with LOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")
    # No stdout: a Stop hook's output is injected back as context and re-invokes
    # the model, causing an endless "(Standing by.)" loop. Side-effect only.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
