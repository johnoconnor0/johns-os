#!/bin/bash
# check-types.sh — Run type checking and linting for the project
# Usage: bash scripts/check-types.sh <project-root>

set -euo pipefail

PROJECT_ROOT="${1:-.}"
cd "$PROJECT_ROOT"

ERRORS=0

echo "=== Type Safety & Static Analysis ==="
echo ""

# --- TypeScript ---
if [ -f "tsconfig.json" ]; then
  echo "--- TypeScript Type Check ---"
  TSC_OUTPUT=$(npx tsc --noEmit 2>&1) && TSC_EXIT=0 || TSC_EXIT=$?
  if [ $TSC_EXIT -ne 0 ]; then
    echo "FAIL: TypeScript errors found"
    echo "$TSC_OUTPUT"
    ERRORS=$((ERRORS + 1))
  else
    echo "PASS: No TypeScript errors"
  fi
  echo ""

  # Check for @ts-ignore / @ts-expect-error / as any abuse
  echo "--- TypeScript Escape Hatches ---"
  TS_IGNORES=$(grep -rn "@ts-ignore\|@ts-expect-error\|as any\|: any" --include="*.ts" --include="*.tsx" . 2>/dev/null | grep -v node_modules | grep -v .git | grep -v dist | grep -v .next || true)
  if [ -n "$TS_IGNORES" ]; then
    TS_COUNT=$(echo "$TS_IGNORES" | wc -l)
    echo "WARNING: $TS_COUNT type escape hatch(es) found — review for legitimacy"
    echo "$TS_IGNORES"
  else
    echo "PASS: No type escape hatches"
  fi
  echo ""
fi

# --- ESLint ---
if [ -f ".eslintrc.js" ] || [ -f ".eslintrc.json" ] || [ -f ".eslintrc.yml" ] || [ -f "eslint.config.js" ] || [ -f "eslint.config.mjs" ] || [ -f "eslint.config.ts" ]; then
  echo "--- ESLint ---"
  LINT_OUTPUT=$(npx eslint . 2>&1) && LINT_EXIT=0 || LINT_EXIT=$?
  if [ $LINT_EXIT -ne 0 ]; then
    echo "FAIL: Lint errors found"
    echo "$LINT_OUTPUT"
    ERRORS=$((ERRORS + 1))
  else
    echo "PASS: No lint errors"
  fi
  echo ""
elif grep -q '"lint"' package.json 2>/dev/null; then
  echo "--- Lint (via package.json script) ---"
  LINT_OUTPUT=$(npm run lint 2>&1) && LINT_EXIT=0 || LINT_EXIT=$?
  if [ $LINT_EXIT -ne 0 ]; then
    echo "FAIL: Lint errors found"
    echo "$LINT_OUTPUT"
    ERRORS=$((ERRORS + 1))
  else
    echo "PASS: No lint errors"
  fi
  echo ""
fi

# --- Python (if applicable) ---
if [ -f "pyproject.toml" ] || [ -f "requirements.txt" ] || [ -f "setup.py" ]; then
  echo "--- Python Type Check ---"
  if command -v mypy &> /dev/null; then
    MYPY_OUTPUT=$(mypy . 2>&1) && MYPY_EXIT=0 || MYPY_EXIT=$?
    if [ $MYPY_EXIT -ne 0 ]; then
      echo "FAIL: mypy errors found"
      echo "$MYPY_OUTPUT"
      ERRORS=$((ERRORS + 1))
    else
      echo "PASS: No mypy errors"
    fi
  elif command -v pyright &> /dev/null; then
    PYRIGHT_OUTPUT=$(pyright . 2>&1) && PYRIGHT_EXIT=0 || PYRIGHT_EXIT=$?
    if [ $PYRIGHT_EXIT -ne 0 ]; then
      echo "FAIL: pyright errors found"
      echo "$PYRIGHT_OUTPUT"
      ERRORS=$((ERRORS + 1))
    else
      echo "PASS: No pyright errors"
    fi
  else
    echo "SKIP: No Python type checker available (install mypy or pyright)"
  fi

  if command -v ruff &> /dev/null; then
    echo ""
    echo "--- Ruff Lint ---"
    RUFF_OUTPUT=$(ruff check . 2>&1) && RUFF_EXIT=0 || RUFF_EXIT=$?
    if [ $RUFF_EXIT -ne 0 ]; then
      echo "FAIL: Ruff errors found"
      echo "$RUFF_OUTPUT"
      ERRORS=$((ERRORS + 1))
    else
      echo "PASS: No Ruff errors"
    fi
  fi
  echo ""
fi

# --- Summary ---
echo "=== Summary ==="
if [ $ERRORS -eq 0 ]; then
  echo "PASS: All type and lint checks passed"
  exit 0
else
  echo "FAIL: $ERRORS check(s) failed"
  exit 1
fi
