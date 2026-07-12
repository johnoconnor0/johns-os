#!/bin/bash
# check-deprecated.sh — Find orphaned files, dead code, commented blocks, and unused deps
# Usage: bash scripts/check-deprecated.sh <project-root>

set -euo pipefail

PROJECT_ROOT="${1:-.}"
cd "$PROJECT_ROOT"

ISSUES=0

echo "=== Deprecated Code & Cleanup Scan ==="
echo ""

# --- Commented-out code blocks (>5 consecutive comment lines) ---
echo "--- Large Commented-Out Code Blocks (>5 lines) ---"
# Find runs of 5+ consecutive single-line comments in TS/JS files
COMMENTED=$(awk '
  /^[[:space:]]*(\/\/|#)/ { count++; next }
  { if (count >= 5) printf "%s (lines %d-%d): %d commented lines\n", FILENAME, NR-count, NR-1, count; count=0 }
  END { if (count >= 5) printf "%s (lines %d-%d): %d commented lines\n", FILENAME, NR-count+1, NR, count }
' $(find . -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" -o -name "*.py" \) | grep -v node_modules | grep -v .git | grep -v dist | grep -v .next | grep -v __pycache__) 2>/dev/null || true)

if [ -n "$COMMENTED" ]; then
  echo "WARNING: Found commented-out code blocks:"
  echo "$COMMENTED"
  ISSUES=$((ISSUES + 1))
else
  echo "PASS: No large commented-out code blocks"
fi
echo ""

# --- Unused dependencies ---
echo "--- Unused Dependencies ---"
if command -v npx &> /dev/null && [ -f "package.json" ]; then
  DEPCHECK_OUTPUT=$(npx depcheck --json 2>/dev/null || echo '{"dependencies":[],"devDependencies":[]}')

  UNUSED_DEPS=$(echo "$DEPCHECK_OUTPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    deps = data.get('dependencies', [])
    dev_deps = data.get('devDependencies', [])
    if deps:
        print('Unused dependencies: ' + ', '.join(deps))
    if dev_deps:
        print('Unused devDependencies: ' + ', '.join(dev_deps))
    if not deps and not dev_deps:
        print('PASS')
except:
    print('SKIP: Could not parse depcheck output')
" 2>/dev/null || echo "SKIP: depcheck parsing failed")

  echo "$UNUSED_DEPS"
  if echo "$UNUSED_DEPS" | grep -q "Unused"; then
    ISSUES=$((ISSUES + 1))
  fi
else
  echo "SKIP: depcheck not available or no package.json"
fi
echo ""

# --- Build artefacts in source ---
echo "--- Build Artefacts in Source ---"
BUILD_DIRS=""
for DIR in dist build .next __pycache__ .turbo; do
  if [ -d "$DIR" ] && [ -d ".git" ]; then
    # Check if it's tracked by git
    TRACKED=$(git ls-files "$DIR" 2>/dev/null | head -1 || true)
    if [ -n "$TRACKED" ]; then
      BUILD_DIRS="$BUILD_DIRS $DIR"
    fi
  fi
done

if [ -n "$BUILD_DIRS" ]; then
  echo "WARNING: Build artefacts committed to repo:$BUILD_DIRS"
  ISSUES=$((ISSUES + 1))
else
  echo "PASS: No build artefacts in source control"
fi
echo ""

# --- console.log / print statements ---
echo "--- Debug Statements ---"
DEBUG_STMTS=$(grep -rn "console\.log\|console\.debug\|console\.warn\|debugger" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" . 2>/dev/null | grep -v node_modules | grep -v .git | grep -v dist | grep -v .next | grep -v "// eslint-disable" | grep -v "\.test\.\|\.spec\.\|__tests__" || true)

if [ -n "$DEBUG_STMTS" ]; then
  DEBUG_COUNT=$(echo "$DEBUG_STMTS" | wc -l)
  echo "WARNING: $DEBUG_COUNT debug statement(s) found in production code"
  echo "$DEBUG_STMTS" | head -30
  if [ "$DEBUG_COUNT" -gt 30 ]; then
    echo "... and $((DEBUG_COUNT - 30)) more"
  fi
  ISSUES=$((ISSUES + 1))
else
  echo "PASS: No debug statements in production code"
fi
echo ""

# --- Stale Supabase migrations ---
echo "--- Supabase Migration Files ---"
if [ -d "supabase/migrations" ]; then
  MIGRATION_COUNT=$(ls supabase/migrations/*.sql 2>/dev/null | wc -l)
  echo "Found $MIGRATION_COUNT migration file(s)"
  ls -la supabase/migrations/*.sql 2>/dev/null
  echo "(Review manually for superseded or conflicting migrations)"
else
  echo "SKIP: No supabase/migrations directory"
fi
echo ""

# --- Summary ---
echo "=== Summary ==="
if [ $ISSUES -eq 0 ]; then
  echo "PASS: No deprecated code issues found"
  exit 0
else
  echo "WARNING: $ISSUES category(ies) flagged for review"
  exit 1
fi
