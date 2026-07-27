#!/usr/bin/env sh
# Drive a real browser from the terminal without requiring a global install.
#
# Wraps `npx --package @playwright/cli playwright-cli`, so the CLI works whether
# or not it is installed globally. A global install is used when present because
# it is faster.
#
# Usage:
#   sh playwright_cli.sh open https://example.com --headed
#   sh playwright_cli.sh snapshot
#   sh playwright_cli.sh click e15
#
# The workflow is always: open -> snapshot -> act on refs from that snapshot ->
# re-snapshot after navigation or a significant DOM change. Element refs go
# stale; a command failing on a missing ref means take a new snapshot.

set -eu

if ! command -v npx >/dev/null 2>&1; then
  echo "npx not found. Install Node.js (which provides npx), then re-run." >&2
  echo "  node --version && npm --version" >&2
  exit 127
fi

if command -v playwright-cli >/dev/null 2>&1; then
  exec playwright-cli "$@"
fi

exec npx --yes --package @playwright/cli playwright-cli "$@"
