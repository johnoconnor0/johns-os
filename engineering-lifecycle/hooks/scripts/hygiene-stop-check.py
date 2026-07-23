#!/usr/bin/env python3
"""Stop hook hygiene reminder."""

from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
REPORT = ROOT / ".project" / ".engineering" / "hygiene" / "hygiene-report.json"


def main() -> int:
    # Stop hooks must stay silent. Any stdout here is injected back into the
    # conversation as context and re-invokes the model, producing an endless
    # "(Standing by.)" loop. Surface hygiene reminders on UserPromptSubmit (the
    # next real turn) instead of on Stop.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
