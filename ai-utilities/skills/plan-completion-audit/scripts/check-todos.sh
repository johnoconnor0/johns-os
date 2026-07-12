#!/bin/bash
# check-todos.sh — Scan for unfinished work markers in source code
# Usage: bash scripts/check-todos.sh <project-root>

set -euo pipefail

PROJECT_ROOT="${1:-.}"
MARKERS="TODO\|FIXME\|HACK\|XXX\|PLACEHOLDER\|TEMP\|STUB\|@todo\|INCOMPLETE\|WIP\|HARDCODED\|WORKAROUND"
EXTENSIONS="--include=*.ts --include=*.tsx --include=*.js --include=*.jsx --include=*.py --include=*.sql --include=*.vue --include=*.svelte --include=*.css --include=*.scss"
EXCLUDES="node_modules\|.git\|dist\|build\|.next\|__pycache__\|venv\|.venv\|coverage\|.turbo"

echo "=== Unfinished Work Marker Scan ==="
echo "Scanning: $PROJECT_ROOT"
echo "---"

RESULTS=$(grep -rn "$MARKERS" $EXTENSIONS "$PROJECT_ROOT" 2>/dev/null | grep -v "$EXCLUDES" || true)

if [ -z "$RESULTS" ]; then
  echo "PASS: No unfinished work markers found."
  exit 0
fi

COUNT=$(echo "$RESULTS" | wc -l)
echo "FOUND: $COUNT unfinished work marker(s)"
echo ""

# Group by marker type for readability
for MARKER in TODO FIXME HACK XXX PLACEHOLDER STUB INCOMPLETE WIP; do
  MARKER_RESULTS=$(echo "$RESULTS" | grep -i "$MARKER" || true)
  if [ -n "$MARKER_RESULTS" ]; then
    MARKER_COUNT=$(echo "$MARKER_RESULTS" | wc -l)
    echo "--- $MARKER ($MARKER_COUNT) ---"
    echo "$MARKER_RESULTS"
    echo ""
  fi
done

exit 1
