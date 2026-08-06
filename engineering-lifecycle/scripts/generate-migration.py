#!/usr/bin/env python3
"""Generate a migration skeleton for one table, in the repo's database dialect.

Produces a timestamped migration with the table definition, foreign keys, and
commented placeholders for indexes. On engines that have row level security it is
enabled with policy placeholders: enabling RLS without policies fails closed,
which is the safe default, and it forces the access rules to be decided rather
than defaulted. On engines that do not have it, emitting those statements would
produce a migration that does not run — so the adapter decides.

Ported from the shelved `database-design` plugin
(ported from a shelved database-design plugin)
so `create-data-model` can emit real DDL instead of prose. That plugin assumed
Supabase; the assumption came across with the port and is what the dialect
adapters remove.

Usage:
    python generate-migration.py users "id uuid PK, name text NOT NULL, email text UNIQUE"
    python generate-migration.py orders "id uuid PK, user_id uuid FK:users.id, total numeric"
    python generate-migration.py products "id serial PK, title text" --dialect mysql
"""

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dialects import DIALECTS, Dialect, resolve_dialect  # noqa: E402


def parse_column(col_def: str) -> dict:
    """Parse a single column definition string into components."""
    parts = col_def.strip().split()
    if len(parts) < 2:
        print(f"Error: Invalid column definition '{col_def}'. Need at least 'name type'.", file=sys.stderr)
        sys.exit(1)

    col = {"name": parts[0], "type": parts[1], "constraints": [], "fk": None, "is_pk": False}

    for part in parts[2:]:
        upper = part.upper()
        if upper == "PK":
            col["is_pk"] = True
        elif part.startswith("FK:"):
            col["fk"] = part[3:]  # e.g., users.id
        else:
            col["constraints"].append(part)

    return col


def generate_sql(table_name: str, columns_str: str, dialect: Dialect) -> str:
    """Generate the full migration SQL for one dialect."""
    raw_cols = [c.strip() for c in columns_str.split(",") if c.strip()]
    columns = [parse_column(c) for c in raw_cols]
    pk_cols = [c["name"] for c in columns if c["is_pk"]]
    qualified = f"{dialect.table_prefix}{table_name}"
    exists_clause = "IF NOT EXISTS " if dialect.supports_if_not_exists else ""

    lines = [
        f"-- Migration: create_{table_name}",
        f"-- Dialect: {dialect.label}",
        f"-- Generated: {datetime.now(UTC).isoformat()}",
        "",
    ]
    lines.append(f"CREATE TABLE {exists_clause}{qualified} (")

    col_lines = []
    for col in columns:
        parts = [f"    {col['name']} {col['type']}"]
        if col["constraints"]:
            parts.append(" ".join(col["constraints"]))
        # Where a foreign key cannot be added later it has to be declared here.
        if col["fk"] and not dialect.supports_alter_add_constraint:
            ref_table, ref_col = col["fk"].split(".", 1)
            parts.append(f"REFERENCES {dialect.table_prefix}{ref_table}({ref_col})")
        col_lines.append(" ".join(parts))

    if pk_cols:
        col_lines.append(f"    PRIMARY KEY ({', '.join(pk_cols)})")

    lines.append(",\n".join(col_lines))
    lines.append(");")
    lines.append("")

    if dialect.supports_alter_add_constraint:
        for col in columns:
            if col["fk"]:
                ref_table, ref_col = col["fk"].split(".", 1)
                lines.append(
                    f"ALTER TABLE {qualified} "
                    f"ADD CONSTRAINT fk_{table_name}_{col['name']} "
                    f"FOREIGN KEY ({col['name']}) REFERENCES {dialect.table_prefix}{ref_table}({ref_col});"
                )
        lines.append("")
    elif any(col["fk"] for col in columns):
        lines.append(f"-- Foreign keys are declared inline above: {dialect.label} cannot add them later.")
        lines.append("-- Enforcement also requires: PRAGMA foreign_keys = ON;")
        lines.append("")

    if dialect.supports_row_level_security:
        lines.extend(_row_level_security_block(table_name, qualified, dialect))
    else:
        lines.append(f"-- {dialect.label} has no row level security.")
        for note in (dialect.access_control_note or "").split(". "):
            if note.strip():
                lines.append(f"-- {note.strip().rstrip('.')}.")
        lines.append("")

    lines.append("-- TODO: Add indexes for common query patterns")
    lines.append(f"-- CREATE INDEX idx_{table_name}_created_at ON {qualified} (created_at);")
    lines.append("")

    return "\n".join(lines)


def _row_level_security_block(table_name: str, qualified: str, dialect: Dialect) -> list[str]:
    """RLS statements, which are spelled differently on the engines that have it."""
    if dialect.name == "sqlserver":
        return [
            "-- TODO: Define a security predicate and policy for row level security.",
            f"-- CREATE FUNCTION dbo.fn_{table_name}_access(@user_id uniqueidentifier)",
            "--     RETURNS TABLE WITH SCHEMABINDING",
            "--     AS RETURN SELECT 1 AS ok WHERE @user_id = CAST(SESSION_CONTEXT(N'user_id') AS uniqueidentifier);",
            f"-- CREATE SECURITY POLICY dbo.{table_name}_policy",
            f"--     ADD FILTER PREDICATE dbo.fn_{table_name}_access(user_id) ON {qualified} WITH (STATE = ON);",
            "",
        ]
    return [
        f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY;",
        "",
        f"-- TODO: Define RLS policies for {table_name}",
        f'-- CREATE POLICY "select_{table_name}" ON {qualified}',
        "--     FOR SELECT USING (auth.uid() = user_id);",
        "",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a migration file in the repo's database dialect.")
    parser.add_argument("table_name", help="Name of the table to create")
    parser.add_argument("columns", help='Column definitions: "name type [PK] [FK:ref] [constraints], ..."')
    parser.add_argument("--output", default=".", help="Output directory (default: current dir)")
    parser.add_argument("--root", default=".", help="Project root used to detect the dialect")
    parser.add_argument(
        "--dialect",
        default="",
        choices=["", *sorted(DIALECTS)],
        help="Database dialect. Defaults to the database detected in context/stack.json.",
    )
    args = parser.parse_args()

    if not re.match(r"^[a-z_][a-z0-9_]*$", args.table_name):
        print("Error: Table name must be lowercase snake_case.", file=sys.stderr)
        sys.exit(1)

    dialect, reason = resolve_dialect(Path(args.root), args.dialect)
    if not dialect.sql:
        print(
            f"Error: {dialect.label} has no DDL migrations ({reason}). "
            f"Model it as schema.json and create collections and indexes from the driver.",
            file=sys.stderr,
        )
        sys.exit(1)

    sql = generate_sql(args.table_name, args.columns, dialect)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_create_{args.table_name}.sql"

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    output_path.write_text(sql, encoding="utf-8")
    print(f"Migration written to: {output_path} ({dialect.label}, from {reason})")


if __name__ == "__main__":
    main()
