#!/usr/bin/env bash
# schema-introspect.sh — Markdown digest of Supabase schema via MCP, or via psql if env-configured.
#
# Usage:
#   bash schema-introspect.sh > schema-digest.md
#
# Detects the available pathway:
#   1. Supabase MCP (if any mcp__*__list_tables-style tool is available in this Claude Code session)
#   2. psql via SUPABASE_DB_URL env var
#   3. Manual fallback: emit a guide for the user to paste schema in
#
# This is a thin shell wrapper: actual MCP calls happen via the skill's tool invocations, not via this script.
# This script's job is to emit:
#   - A note about which pathway was detected
#   - A template for capturing the digest
#
# The skill that calls this script is responsible for the actual data fetch.

set -e

echo "# Schema Digest"
echo
echo "**Generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

if [ -n "${SUPABASE_DB_URL:-}" ] && command -v psql >/dev/null 2>&1; then
  echo "**Source:** psql via SUPABASE_DB_URL"
  echo
  echo "## Tables (public schema)"
  echo
  echo '```sql'
  psql "$SUPABASE_DB_URL" -c "
    SELECT table_name,
           (SELECT count(*) FROM information_schema.columns c WHERE c.table_name = t.table_name) AS columns
    FROM information_schema.tables t
    WHERE table_schema = 'public'
    ORDER BY table_name;
  " 2>/dev/null || echo "Connection failed — provide schema manually."
  echo '```'
  echo
  echo "## Extensions"
  echo
  echo '```sql'
  psql "$SUPABASE_DB_URL" -c "SELECT extname, extversion FROM pg_extension ORDER BY extname;" 2>/dev/null || true
  echo '```'
  echo
  echo "## Migrations"
  echo
  echo '```sql'
  psql "$SUPABASE_DB_URL" -c "SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version DESC LIMIT 20;" 2>/dev/null || echo "(no supabase_migrations table)"
  echo '```'
elif [ -n "${CLAUDE_MCP_SUPABASE:-}" ]; then
  echo "**Source:** Supabase MCP (use the calling skill to invoke list_tables / list_extensions / list_migrations directly)"
  echo
  echo "## Tables, extensions, migrations"
  echo
  echo "Use the skill's Read/Bash tool invocations to call mcp__*__list_tables, etc. This script is informational."
else
  echo "**Source:** Manual — please paste schema below"
  echo
  echo "## Tables"
  echo
  echo '```'
  echo '<paste output of: \dt or SELECT * FROM information_schema.tables WHERE table_schema = ''public'' here>'
  echo '```'
  echo
  echo "## Extensions"
  echo
  echo '```'
  echo '<paste output of: \dx>'
  echo '```'
fi
