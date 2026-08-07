#!/usr/bin/env python3
"""Stop hook hygiene reminder."""

from __future__ import annotations


def main() -> int:
    # `ROOT` and `REPORT` used to be computed here from a bare `Path.cwd()`. They
    # were never read, and their only effect was to suggest to the next reader
    # that this hook inspects the hygiene report. It does not.
    # Stop hooks must stay silent. Any stdout here is injected back into the
    # conversation as context and re-invokes the model, producing an endless
    # "(Standing by.)" loop. Surface hygiene reminders on UserPromptSubmit (the
    # next real turn) instead of on Stop.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
