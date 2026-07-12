#!/bin/bash
# check-secrets.sh — Scan for hardcoded secrets, API keys, and credentials
# Usage: bash scripts/check-secrets.sh <project-root>

set -euo pipefail

PROJECT_ROOT="${1:-.}"
cd "$PROJECT_ROOT"

ISSUES=0

echo "=== Secrets & Credentials Scan ==="
echo ""

# --- Hardcoded secrets in source ---
echo "--- Hardcoded Secrets ---"
SECRET_PATTERNS="password\s*[=:]\|api_key\s*[=:]\|apiKey\s*[=:]\|secret\s*[=:]\|token\s*[=:]\|PRIVATE_KEY\|SUPABASE_SERVICE_ROLE_KEY\s*[=:]\|DATABASE_URL\s*[=:]\|OPENAI_API_KEY\s*[=:]\|ANTHROPIC_API_KEY\s*[=:]\|STRIPE_SECRET\|AWS_SECRET"

SECRETS=$(grep -rn "$SECRET_PATTERNS" \
  --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
  --include="*.py" --include="*.yaml" --include="*.yml" --include="*.json" \
  --include="*.toml" --include="*.cfg" --include="*.ini" \
  . 2>/dev/null \
  | grep -v node_modules | grep -v .git | grep -v dist | grep -v .next \
  | grep -v "package-lock.json\|yarn.lock\|pnpm-lock" \
  | grep -v "\.d\.ts" \
  | grep -v "process\.env\|import\.meta\.env\|os\.environ\|os\.getenv" \
  | grep -v "example\|sample\|template\|placeholder\|CHANGEME\|your-.*-here\|<.*>" \
  || true)

if [ -n "$SECRETS" ]; then
  SECRET_COUNT=$(echo "$SECRETS" | wc -l)
  echo "CRITICAL: $SECRET_COUNT potential hardcoded secret(s) found — review each one:"
  echo "$SECRETS"
  ISSUES=$((ISSUES + 1))
else
  echo "PASS: No obvious hardcoded secrets"
fi
echo ""

# --- .env files in git ---
echo "--- .env Files in Version Control ---"
if [ -d ".git" ]; then
  ENV_TRACKED=$(git ls-files | grep "\.env" | grep -v "\.env\.example\|\.env\.sample\|\.env\.template" || true)
  if [ -n "$ENV_TRACKED" ]; then
    echo "CRITICAL: .env files tracked in git:"
    echo "$ENV_TRACKED"
    ISSUES=$((ISSUES + 1))
  else
    echo "PASS: No .env files tracked in git"
  fi
else
  echo "SKIP: Not a git repository"
fi
echo ""

# --- .gitignore coverage ---
echo "--- .gitignore Coverage ---"
if [ -f ".gitignore" ]; then
  MISSING_IGNORES=""
  for PATTERN in ".env" ".env.local" ".env.production" "*.pem" "*.key" "service-account*.json"; do
    if ! grep -q "$PATTERN" .gitignore 2>/dev/null; then
      MISSING_IGNORES="$MISSING_IGNORES $PATTERN"
    fi
  done
  if [ -n "$MISSING_IGNORES" ]; then
    echo "WARNING: .gitignore may be missing patterns:$MISSING_IGNORES"
    ISSUES=$((ISSUES + 1))
  else
    echo "PASS: .gitignore covers common secret patterns"
  fi
else
  echo "WARNING: No .gitignore file found"
  ISSUES=$((ISSUES + 1))
fi
echo ""

# --- Supabase service role key exposure ---
echo "--- Supabase Service Role Key ---"
SERVICE_ROLE_CLIENT=$(grep -rn "supabase_service_role\|service_role\|serviceRole\|SERVICE_ROLE" \
  --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
  . 2>/dev/null \
  | grep -v node_modules | grep -v .git | grep -v dist | grep -v .next \
  | grep -v "\.d\.ts\|\.env\|\.example" \
  || true)

if [ -n "$SERVICE_ROLE_CLIENT" ]; then
  # Check if any of these are in client-side code (src/app, src/components, pages/, app/)
  CLIENT_SIDE=$(echo "$SERVICE_ROLE_CLIENT" | grep -E "(src/app|src/components|pages/|app/|components/)" | grep -v "api/\|server\|middleware\|route\.ts\|route\.js" || true)
  if [ -n "$CLIENT_SIDE" ]; then
    echo "CRITICAL: Service role key may be exposed in client-side code:"
    echo "$CLIENT_SIDE"
    ISSUES=$((ISSUES + 1))
  else
    echo "PASS: Service role key references are server-side only"
  fi
else
  echo "PASS: No service role key references in source"
fi
echo ""

# --- npm audit ---
echo "--- Dependency Vulnerabilities ---"
if [ -f "package.json" ]; then
  AUDIT_OUTPUT=$(npm audit --json 2>/dev/null || echo '{}')
  VULN_COUNT=$(echo "$AUDIT_OUTPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    vulns = data.get('metadata', {}).get('vulnerabilities', {})
    critical = vulns.get('critical', 0)
    high = vulns.get('high', 0)
    moderate = vulns.get('moderate', 0)
    total = critical + high + moderate
    if total > 0:
        print(f'FOUND: {critical} critical, {high} high, {moderate} moderate vulnerabilities')
    else:
        print('PASS')
except:
    print('SKIP: Could not parse npm audit output')
" 2>/dev/null || echo "SKIP: npm audit parsing failed")

  echo "$VULN_COUNT"
  if echo "$VULN_COUNT" | grep -q "FOUND"; then
    ISSUES=$((ISSUES + 1))
    echo "Run 'npm audit' for details"
  fi
else
  echo "SKIP: No package.json"
fi
echo ""

# --- Summary ---
echo "=== Summary ==="
if [ $ISSUES -eq 0 ]; then
  echo "PASS: No security issues found"
  exit 0
else
  echo "FAIL: $ISSUES security category(ies) flagged"
  exit 1
fi
