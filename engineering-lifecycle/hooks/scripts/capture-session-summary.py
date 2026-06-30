#!/usr/bin/env python3
"""Capture a small stop-hook event for lifecycle observability."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path.cwd()
LOG = ROOT / ".project" / ".engineering" / "reports" / "session-events.jsonl"


def main() -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {"at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "event": "session_stop"}
    with LOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")
    # No stdout: a Stop hook's output is injected back as context and re-invokes
    # the model, causing an endless "(Standing by.)" loop. Side-effect only.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
