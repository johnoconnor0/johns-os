#!/usr/bin/env bash
# schema-introspect.sh — Markdown digest of a live database schema, whatever the engine.
#
# Usage:
#   bash schema-introspect.sh > schema-digest.md
#   DATABASE_URL=postgres://... bash schema-introspect.sh
#   bash schema-introspect.sh --dialect mysql
#
# The connection string is read from DATABASE_URL. Engine-specific variables are
# accepted as aliases so an existing environment keeps working: POSTGRES_URL,
# SUPABASE_DB_URL, MYSQL_URL, MSSQL_URL, MONGODB_URI, SQLITE_PATH.
#
# The engine is taken from --dialect, or inferred from the connection string's
# scheme, or from the database recorded in .project/.engineering/context/stack.json.
# This script used to accept only SUPABASE_DB_URL and speak only psql, so a repo on
# MySQL, SQLite, SQL Server or Mongo had no introspection path at all and fell
# through to "paste it in by hand".
#
# This is a thin wrapper. The calling skill is responsible for the actual data fetch
# when the pathway is an MCP server rather than a CLI client.

set -e

DIALECT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dialect) DIALECT="$2"; shift 2 ;;
    --dialect=*) DIALECT="${1#*=}"; shift ;;
    *) shift ;;
  esac
done

DSN="${DATABASE_URL:-}"
[ -n "$DSN" ] || DSN="${POSTGRES_URL:-}"
[ -n "$DSN" ] || DSN="${SUPABASE_DB_URL:-}"
[ -n "$DSN" ] || DSN="${MYSQL_URL:-}"
[ -n "$DSN" ] || DSN="${MSSQL_URL:-}"
[ -n "$DSN" ] || DSN="${MONGODB_URI:-}"
[ -n "$DSN" ] || DSN="${SQLITE_PATH:-}"

# Infer the engine from the connection scheme when it was not stated.
if [ -z "$DIALECT" ] && [ -n "$DSN" ]; then
  case "$DSN" in
    postgres://*|postgresql://*) DIALECT=postgresql ;;
    mysql://*|mariadb://*)       DIALECT=mysql ;;
    sqlserver://*|mssql://*)     DIALECT=sqlserver ;;
    mongodb://*|mongodb+srv://*) DIALECT=mongodb ;;
    file:*|*.sqlite|*.sqlite3|*.db) DIALECT=sqlite ;;
  esac
fi

# Fall back to whatever detect-stack recorded for this repo.
STACK=".project/.engineering/context/stack.json"
if [ -z "$DIALECT" ] && [ -f "$STACK" ]; then
  case "$(tr '[:upper:]' '[:lower:]' < "$STACK")" in
    *mongodb*)    DIALECT=mongodb ;;
    *mysql*|*mariadb*) DIALECT=mysql ;;
    *sqlite*)     DIALECT=sqlite ;;
    *"sql server"*|*mssql*) DIALECT=sqlserver ;;
    *postgres*|*supabase*)  DIALECT=postgresql ;;
  esac
fi

echo "# Schema Digest"
echo
echo "**Generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "**Dialect:** ${DIALECT:-unknown}"
echo

emit_manual() {
  echo "**Source:** Manual — please paste schema below"
  echo
  echo "_No connection string in DATABASE_URL and no client on PATH for ${DIALECT:-this engine}._"
  echo
  echo "## Tables"
  echo
  echo '```'
  echo '<paste the table list here>'
  echo '```'
  echo
  echo "## Indexes and constraints"
  echo
  echo '```'
  echo '<paste index and constraint definitions here>'
  echo '```'
}

if [ -z "$DSN" ]; then
  if [ -n "${CLAUDE_MCP_SUPABASE:-}" ]; then
    echo "**Source:** Supabase MCP (call list_tables / list_extensions / list_migrations from the skill)"
    echo
    echo "This script is informational; the skill performs the fetch."
    exit 0
  fi
  emit_manual
  exit 0
fi

case "$DIALECT" in
  postgresql)
    if command -v psql >/dev/null 2>&1; then
      echo "**Source:** psql"
      echo
      echo "## Tables (public schema)"
      echo '```'
      psql "$DSN" -c "
        SELECT table_name,
               (SELECT count(*) FROM information_schema.columns c WHERE c.table_name = t.table_name) AS columns
        FROM information_schema.tables t
        WHERE table_schema = 'public'
        ORDER BY table_name;
      " 2>/dev/null || echo "Connection failed — provide schema manually."
      echo '```'
      echo
      echo "## Extensions"
      echo '```'
      psql "$DSN" -c "SELECT extname, extversion FROM pg_extension ORDER BY extname;" 2>/dev/null || true
      echo '```'
      echo
      echo "## Migrations"
      echo '```'
      # supabase_migrations exists only on Supabase; fall back to a common table name.
      psql "$DSN" -c "SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version DESC LIMIT 20;" 2>/dev/null \
        || psql "$DSN" -c "SELECT * FROM schema_migrations ORDER BY 1 DESC LIMIT 20;" 2>/dev/null \
        || echo "(no recognised migrations table)"
      echo '```'
    else
      emit_manual
    fi
    ;;
  mysql)
    if command -v mysql >/dev/null 2>&1; then
      echo "**Source:** mysql"
      echo
      echo "## Tables"
      echo '```'
      mysql --table "$DSN" -e "
        SELECT TABLE_NAME, TABLE_ROWS,
               (SELECT COUNT(*) FROM information_schema.COLUMNS c
                 WHERE c.TABLE_NAME = t.TABLE_NAME AND c.TABLE_SCHEMA = DATABASE()) AS columns
        FROM information_schema.TABLES t
        WHERE t.TABLE_SCHEMA = DATABASE()
        ORDER BY TABLE_NAME;
      " 2>/dev/null || echo "Connection failed — provide schema manually."
      echo '```'
      echo
      echo "## Foreign keys"
      echo '```'
      mysql --table "$DSN" -e "
        SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY TABLE_NAME;
      " 2>/dev/null || true
      echo '```'
    else
      emit_manual
    fi
    ;;
  sqlite)
    if command -v sqlite3 >/dev/null 2>&1; then
      echo "**Source:** sqlite3"
      echo
      echo "## Schema"
      echo '```sql'
      sqlite3 "${DSN#file:}" ".schema" 2>/dev/null || echo "Could not open database — provide schema manually."
      echo '```'
      echo
      echo "## Tables"
      echo '```'
      sqlite3 "${DSN#file:}" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;" 2>/dev/null || true
      echo '```'
    else
      emit_manual
    fi
    ;;
  sqlserver)
    if command -v sqlcmd >/dev/null 2>&1; then
      echo "**Source:** sqlcmd"
      echo
      echo "## Tables"
      echo '```'
      sqlcmd -S "$DSN" -Q "
        SELECT t.name AS table_name, COUNT(c.name) AS columns
        FROM sys.tables t LEFT JOIN sys.columns c ON c.object_id = t.object_id
        GROUP BY t.name ORDER BY t.name;
      " 2>/dev/null || echo "Connection failed — provide schema manually."
      echo '```'
      echo
      echo "## Foreign keys"
      echo '```'
      sqlcmd -S "$DSN" -Q "
        SELECT fk.name, OBJECT_NAME(fk.parent_object_id) AS from_table,
               OBJECT_NAME(fk.referenced_object_id) AS to_table
        FROM sys.foreign_keys fk ORDER BY fk.name;
      " 2>/dev/null || true
      echo '```'
    else
      emit_manual
    fi
    ;;
  mongodb)
    if command -v mongosh >/dev/null 2>&1; then
      echo "**Source:** mongosh"
      echo
      echo "_Document store: collections and inferred field shapes, not a fixed schema._"
      echo
      echo "## Collections"
      echo '```'
      mongosh "$DSN" --quiet --eval '
        db.getCollectionNames().forEach(function (name) {
          var doc = db.getCollection(name).findOne() || {};
          print(name + ": " + Object.keys(doc).join(", "));
        });
      ' 2>/dev/null || echo "Connection failed — provide collections manually."
      echo '```'
      echo
      echo "## Indexes"
      echo '```'
      mongosh "$DSN" --quiet --eval '
        db.getCollectionNames().forEach(function (name) {
          db.getCollection(name).getIndexes().forEach(function (index) {
            print(name + ": " + index.name + " " + JSON.stringify(index.key));
          });
        });
      ' 2>/dev/null || true
      echo '```'
    else
      emit_manual
    fi
    ;;
  *)
    emit_manual
    ;;
esac
