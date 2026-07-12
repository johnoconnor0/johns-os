#!/usr/bin/env bash
# verify-stack.sh — Detect the project stack and run the appropriate verifier.
#
# Usage:
#   bash verify-stack.sh [--dry-run]
#
# Runs from the repo root (caller's cwd). Detects via file presence (priority order).
# Exits 0 if all detected verifiers pass; non-zero if any fail.
#
# --dry-run: print which verifiers would run, but don't run them.

set -e

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
fi

VERIFIERS=()
FAILURES=()

# Detection priority — plugin marketplace first (most specific)
if [ -f "scripts/check-versions.mjs" ]; then
  VERIFIERS+=("node scripts/check-versions.mjs")
fi

if [ -d "tests" ] && find tests -name "*.py" -type f | head -1 | grep -q .; then
  # Python test discovery
  if [ -f "tests/scripts/test_smoke.py" ]; then
    VERIFIERS+=("python tests/scripts/test_smoke.py")
  elif command -v pytest >/dev/null 2>&1; then
    VERIFIERS+=("python -m pytest tests/")
  fi
fi

if [ -f "package.json" ] && [ -f "tsconfig.json" ]; then
  if command -v npx >/dev/null 2>&1; then
    VERIFIERS+=("npx tsc --noEmit")
  fi
fi

if [ -f "package.json" ]; then
  if grep -q '"build"' package.json 2>/dev/null; then
    VERIFIERS+=("npm run build")
  fi
  if grep -q '"test"' package.json 2>/dev/null; then
    VERIFIERS+=("npm test")
  fi
fi

if [ -f "Cargo.toml" ]; then
  VERIFIERS+=("cargo check")
  VERIFIERS+=("cargo test")
fi

if [ -f "go.mod" ]; then
  VERIFIERS+=("go vet ./...")
  VERIFIERS+=("go test ./...")
fi

if [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; then
  # Only add pytest if we didn't already add from tests/ directory check
  if ! printf '%s\n' "${VERIFIERS[@]}" | grep -q pytest; then
    if command -v pytest >/dev/null 2>&1; then
      VERIFIERS+=("python -m pytest")
    fi
  fi
  if [ -f "mypy.ini" ] || grep -q "\[tool.mypy\]" pyproject.toml 2>/dev/null; then
    if command -v mypy >/dev/null 2>&1; then
      VERIFIERS+=("mypy .")
    fi
  fi
fi

if [ "${#VERIFIERS[@]}" -eq 0 ]; then
  echo "verify-stack: no verifiers detected" >&2
  echo "Mark batch findings as 'applied unverified' in the ledger." >&2
  exit 0
fi

echo "verify-stack: detected verifiers ($((${#VERIFIERS[@]}))):"
for v in "${VERIFIERS[@]}"; do
  echo "  - $v"
done

if [ "$DRY_RUN" -eq 1 ]; then
  echo "(dry-run; not executed)"
  exit 0
fi

# Run each verifier; capture failures
for v in "${VERIFIERS[@]}"; do
  echo ""
  echo "--- $v ---"
  if ! eval "$v"; then
    FAILURES+=("$v")
  fi
done

if [ "${#FAILURES[@]}" -gt 0 ]; then
  echo ""
  echo "verify-stack: FAILED — $((${#FAILURES[@]})) verifier(s) failed:" >&2
  for f in "${FAILURES[@]}"; do
    echo "  - $f" >&2
  done
  exit 1
fi

echo ""
echo "verify-stack: all ${#VERIFIERS[@]} verifiers passed"
exit 0
