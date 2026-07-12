#!/bin/bash
# check-unused-deps.sh — Find unused dependencies and unreferenced exports
# Usage: bash scripts/check-unused-deps.sh <project-root>

set -euo pipefail

PROJECT_ROOT="${1:-.}"
cd "$PROJECT_ROOT"

ISSUES=0

echo "=== Unused Dependencies & Exports Scan ==="
echo ""

# --- Unused npm dependencies ---
echo "--- Unused npm Dependencies ---"
if [ -f "package.json" ] && command -v npx &> /dev/null; then
  DEPCHECK_OUTPUT=$(npx depcheck 2>&1 || true)
  echo "$DEPCHECK_OUTPUT"
  if echo "$DEPCHECK_OUTPUT" | grep -q "Unused\|Missing"; then
    ISSUES=$((ISSUES + 1))
  fi
else
  echo "SKIP: No package.json or npx not available"
fi
echo ""

# --- Unreferenced source files ---
echo "--- Potentially Orphaned Source Files ---"
echo "(Files not imported by any other file — review manually, entry points and configs are expected here)"

# Build a list of all TS/JS source files
ALL_FILES=$(find . -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \) \
  | grep -v node_modules | grep -v .git | grep -v dist | grep -v .next | grep -v __pycache__ \
  | grep -v "\.test\.\|\.spec\.\|__tests__\|\.config\.\|\.d\.ts" \
  | sort)

ORPHAN_COUNT=0
for FILE in $ALL_FILES; do
  BASENAME=$(basename "$FILE" | sed 's/\.[^.]*$//')

  # Skip known entry points and config files
  if echo "$BASENAME" | grep -qE "^(index|main|app|layout|page|middleware|next\.config|tailwind|postcss|jest|vitest|tsconfig|eslint|prettier)"; then
    continue
  fi

  # Check if this file is imported anywhere else
  IMPORT_CHECK=$(grep -rl "$BASENAME" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" . 2>/dev/null \
    | grep -v node_modules | grep -v .git | grep -v dist | grep -v .next \
    | grep -v "$FILE" \
    | head -1 || true)

  if [ -z "$IMPORT_CHECK" ]; then
    echo "  ORPHAN?: $FILE"
    ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
  fi
done

if [ $ORPHAN_COUNT -eq 0 ]; then
  echo "  PASS: No orphaned files detected"
else
  echo ""
  echo "  Found $ORPHAN_COUNT potentially orphaned file(s) — verify these are genuinely unused"
  ISSUES=$((ISSUES + 1))
fi
echo ""

# --- Circular dependencies ---
echo "--- Circular Dependencies ---"
if command -v npx &> /dev/null; then
  SRC_DIR="src"
  [ ! -d "$SRC_DIR" ] && SRC_DIR="app"
  [ ! -d "$SRC_DIR" ] && SRC_DIR="."

  CIRCULAR_OUTPUT=$(npx madge --circular --extensions ts,tsx,js,jsx "$SRC_DIR" 2>/dev/null || echo "SKIP: madge not available")
  echo "$CIRCULAR_OUTPUT"
  if echo "$CIRCULAR_OUTPUT" | grep -q "Found [1-9]"; then
    ISSUES=$((ISSUES + 1))
  fi
else
  echo "SKIP: npx not available"
fi
echo ""

# --- Summary ---
echo "=== Summary ==="
if [ $ISSUES -eq 0 ]; then
  echo "PASS: No unused dependency issues found"
  exit 0
else
  echo "WARNING: $ISSUES category(ies) flagged for review"
  exit 1
fi
