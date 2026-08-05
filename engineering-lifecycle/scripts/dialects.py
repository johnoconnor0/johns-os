#!/usr/bin/env python3
"""Database dialect adapters for the data model tooling.

`create-data-model` was ported from a shelved Supabase-specific plugin and kept
its assumptions: the parser read PostgreSQL DDL, stamped `"dialect": "postgresql"`
on every model regardless, warned about row level security on engines that have no
such concept, and introspected through `psql` or the Supabase MCP or not at all.
Stack detection has recognised MySQL, SQLite, MongoDB and Postgres since 0.7.1, and
the skill claimed to read the detected database as its first input — then ignored it.

An adapter carries what actually differs between engines: how identifiers are
quoted, whether enums are a declared type or a column type, which keywords end a
column's type, whether row level security exists at all, and how to introspect a
live database. Everything else in the pipeline stays shared, exactly as the design
system adapters share one token contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from eng_common import engineering_root

# Tokens that end a column's type in every SQL dialect.
_COMMON_COLUMN_KEYWORDS = frozenset(
    {"PRIMARY", "NOT", "NULL", "UNIQUE", "REFERENCES", "DEFAULT", "CHECK", "GENERATED", "CONSTRAINT", "COLLATE"}
)


@dataclass(frozen=True)
class Dialect:
    """One database engine's answer to the questions the shared tooling asks."""

    name: str
    label: str
    # A document store has no DDL to parse; its model comes from a collection spec.
    sql: bool = True
    # Characters an identifier may be wrapped in: "user" / `user` / [user].
    quote_chars: str = '"'
    # Written in front of a table in generated DDL, e.g. `public.` on Postgres.
    table_prefix: str = ""
    # `CREATE TYPE x AS ENUM (...)` as a standalone object.
    declared_enums: bool = False
    # `ENUM('a','b')` written inline as a column type.
    inline_enums: bool = False
    supports_row_level_security: bool = False
    supports_if_not_exists: bool = True
    # SQLite cannot add a foreign key after the fact; it must be declared inline in
    # CREATE TABLE. A migration using ALTER TABLE ... ADD CONSTRAINT simply fails there.
    supports_alter_add_constraint: bool = True
    # How a generated primary key is spelled.
    identity_column: str = "uuid PRIMARY KEY"
    # Extra tokens that terminate a column type in this dialect only.
    extra_column_keywords: frozenset[str] = frozenset()
    # Client used to introspect a live database, and the env var holding its DSN.
    client: str = ""
    dsn_env: tuple[str, ...] = ()
    migration_sources: tuple[str, ...] = ()
    notes: str = ""
    # What to do instead, on engines with no row level security. "Use grants" is
    # wrong for SQLite, which has no users at all.
    access_control_note: str = ""

    @property
    def column_keywords(self) -> frozenset[str]:
        return _COMMON_COLUMN_KEYWORDS | self.extra_column_keywords


POSTGRESQL = Dialect(
    name="postgresql",
    label="PostgreSQL",
    quote_chars='"',
    table_prefix="public.",
    declared_enums=True,
    supports_row_level_security=True,
    identity_column="uuid PRIMARY KEY DEFAULT gen_random_uuid()",
    client="psql",
    dsn_env=("DATABASE_URL", "POSTGRES_URL", "SUPABASE_DB_URL"),
    migration_sources=("supabase/migrations/*.sql", "migrations/*.sql", "db/migrate/*.sql"),
    notes="Row level security and declared enum types are Postgres features; Supabase speaks this dialect.",
)

MYSQL = Dialect(
    name="mysql",
    label="MySQL / MariaDB",
    quote_chars='"`',
    inline_enums=True,
    supports_row_level_security=False,
    identity_column="BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY",
    # UNSIGNED and ZEROFILL are part of the type, not constraints, so they are
    # deliberately absent — breaking on them would record `BIGINT` for a
    # `BIGINT UNSIGNED` column and quietly halve its range in the model.
    extra_column_keywords=frozenset({"AUTO_INCREMENT", "COMMENT", "CHARACTER", "CHARSET", "ON"}),
    client="mysql",
    dsn_env=("DATABASE_URL", "MYSQL_URL"),
    migration_sources=("migrations/*.sql", "db/migrate/*.sql"),
    notes="No row level security. Enums are a column type, not a declared type. Grants replace policies.",
    access_control_note=(
        "Restrict access with GRANTs on a dedicated application user, "
        "and enforce per-row rules in the application or through views."
    ),
)

SQLITE = Dialect(
    name="sqlite",
    label="SQLite",
    quote_chars='"`[]',
    supports_row_level_security=False,
    supports_alter_add_constraint=False,
    identity_column="INTEGER PRIMARY KEY AUTOINCREMENT",
    extra_column_keywords=frozenset({"AUTOINCREMENT", "ON", "CONFLICT"}),
    client="sqlite3",
    dsn_env=("DATABASE_URL", "SQLITE_PATH"),
    migration_sources=("migrations/*.sql", "db/migrate/*.sql"),
    notes="No enums, no row level security, no schemas. Constrain a value set with CHECK instead.",
    # Kept ASCII: this text is emitted into generated .sql files, which are read by
    # migration runners and terminals with no guaranteed encoding.
    access_control_note=(
        "SQLite has no users, roles or grants; the database is a file. "
        "Access control is filesystem permissions plus whatever the application enforces."
    ),
)

SQLSERVER = Dialect(
    name="sqlserver",
    label="SQL Server",
    quote_chars='"[]',
    table_prefix="dbo.",
    supports_row_level_security=True,
    supports_if_not_exists=False,
    identity_column="uniqueidentifier NOT NULL PRIMARY KEY DEFAULT NEWID()",
    extra_column_keywords=frozenset({"IDENTITY", "ROWGUIDCOL", "SPARSE"}),
    client="sqlcmd",
    dsn_env=("DATABASE_URL", "MSSQL_URL", "SQLSERVER_URL"),
    migration_sources=("migrations/*.sql",),
    notes=(
        "Row level security exists but is built from security policies and predicate functions, "
        "not Postgres CREATE POLICY. No CREATE TABLE IF NOT EXISTS."
    ),
)

MONGODB = Dialect(
    name="mongodb",
    label="MongoDB",
    sql=False,
    supports_if_not_exists=False,
    identity_column="_id objectId",
    client="mongosh",
    dsn_env=("DATABASE_URL", "MONGODB_URI", "MONGO_URL"),
    migration_sources=("migrations/*.js", "migrations/*.json"),
    notes=(
        "Document store: there is no DDL to parse. The model is authored as `schema.json` "
        "(collections and fields) rather than `schema.sql`, and validation lives in a JSON Schema validator."
    ),
)

DIALECTS: dict[str, Dialect] = {d.name: d for d in (POSTGRESQL, MYSQL, SQLITE, SQLSERVER, MONGODB)}

DEFAULT_DIALECT = POSTGRESQL

# What `context/stack.json` calls a database, mapped to the adapter that models it.
# ORMs are deliberately absent: Prisma or Drizzle says nothing about the engine
# underneath, so an ORM alone must not decide the dialect.
_STACK_DATABASE_TO_DIALECT = {
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "supabase": "postgresql",
    "neon": "postgresql",
    "cockroachdb": "postgresql",
    "timescaledb": "postgresql",
    "mysql": "mysql",
    "mariadb": "mysql",
    "planetscale": "mysql",
    "sqlite": "sqlite",
    "libsql": "sqlite",
    "turso": "sqlite",
    "d1": "sqlite",
    "cloudflare d1": "sqlite",
    "sql server": "sqlserver",
    "sqlserver": "sqlserver",
    "mssql": "sqlserver",
    "azure sql": "sqlserver",
    "mongodb": "mongodb",
    "mongo": "mongodb",
}

# Keys are already normalised: lowercased, with separators removed.
_ALIASES = {
    "pg": "postgresql",
    "postgres": "postgresql",
    "supabase": "postgresql",
    "maria": "mysql",
    "mariadb": "mysql",
    "mssql": "sqlserver",
    "azuresql": "sqlserver",
    "mongo": "mongodb",
    "lite": "sqlite",
}


def get_dialect(name: str | None) -> Dialect:
    """Look up a dialect by canonical name or common alias."""
    if not name:
        return DEFAULT_DIALECT
    key = "".join(char for char in str(name).strip().lower() if char.isalnum())
    return DIALECTS.get(_ALIASES.get(key, key), DEFAULT_DIALECT)


def detected_databases(root: Path) -> list[str]:
    """Databases `detect-stack` recorded for this repo."""
    path = engineering_root(root) / "context" / "stack.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    found = data.get("database")
    return [str(item) for item in found] if isinstance(found, list) else []


def resolve_dialect(root: Path, override: str | None = None) -> tuple[Dialect, str]:
    """The dialect to model in, and the evidence for choosing it.

    An explicit override always wins. Otherwise the answer comes from the database
    `detect-stack` already found, which is the input the skill always claimed to
    read. Returning the reason alongside means a wrong guess is visible in the
    output rather than silently shaping the schema.
    """
    if override:
        dialect = get_dialect(override)
        return dialect, f"--dialect {override}"
    databases = detected_databases(root)
    for database in databases:
        mapped = _STACK_DATABASE_TO_DIALECT.get(database.strip().lower())
        if mapped:
            return DIALECTS[mapped], f"context/stack.json database: {database}"
    if databases:
        return DEFAULT_DIALECT, f"no adapter for detected database(s) {', '.join(databases)}; defaulted"
    return DEFAULT_DIALECT, "no database detected; defaulted"


def model_filename(dialect: Dialect) -> str:
    """What the human authors for this engine: DDL, or a collection spec."""
    return "schema.sql" if dialect.sql else "schema.json"
