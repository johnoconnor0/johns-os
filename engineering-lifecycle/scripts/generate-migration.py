#!/usr/bin/env python3
"""Generate a PostgreSQL/Supabase migration skeleton for one table.

Produces a timestamped migration with the table definition, foreign keys, RLS
enabled, and commented placeholders for policies and indexes. The placeholders
are deliberate: enabling RLS without policies fails closed, which is the safe
default, and it forces the access rules to be decided rather than defaulted.

Ported from the shelved `database-design` plugin
(`_unreleased/engineering/database-design/skills/business-data-model-designer/`)
so `create-data-model` can emit real DDL instead of prose.

Usage:
    python generate-migration.py users "id uuid PK, name text NOT NULL, email text UNIQUE"
    python generate-migration.py orders "id uuid PK, user_id uuid FK:users.id, total numeric"
    python generate-migration.py products "id serial PK, title text, price numeric" --output ./migrations
"""

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path


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


def generate_sql(table_name: str, columns_str: str) -> str:
    """Generate the full migration SQL."""
    raw_cols = [c.strip() for c in columns_str.split(",") if c.strip()]
    columns = [parse_column(c) for c in raw_cols]
    pk_cols = [c["name"] for c in columns if c["is_pk"]]

    lines = [f"-- Migration: create_{table_name}", f"-- Generated: {datetime.now(UTC).isoformat()}", ""]
    lines.append(f"CREATE TABLE IF NOT EXISTS public.{table_name} (")

    col_lines = []
    for col in columns:
        parts = [f"    {col['name']} {col['type']}"]
        if col["constraints"]:
            parts.append(" ".join(col["constraints"]))
        col_lines.append(" ".join(parts))

    if pk_cols:
        col_lines.append(f"    PRIMARY KEY ({', '.join(pk_cols)})")

    lines.append(",\n".join(col_lines))
    lines.append(");")
    lines.append("")

    # Foreign keys
    for col in columns:
        if col["fk"]:
            ref_table, ref_col = col["fk"].split(".", 1)
            lines.append(
                f"ALTER TABLE public.{table_name} "
                f"ADD CONSTRAINT fk_{table_name}_{col['name']} "
                f"FOREIGN KEY ({col['name']}) REFERENCES public.{ref_table}({ref_col});"
            )
    lines.append("")

    # RLS
    lines.append(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY;")
    lines.append("")
    lines.append(f"-- TODO: Define RLS policies for {table_name}")
    lines.append(f'-- CREATE POLICY "select_{table_name}" ON public.{table_name}')
    lines.append("--     FOR SELECT USING (auth.uid() = user_id);")
    lines.append("")

    # Index placeholder
    lines.append("-- TODO: Add indexes for common query patterns")
    lines.append(f"-- CREATE INDEX idx_{table_name}_created_at ON public.{table_name} (created_at);")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Supabase migration file.")
    parser.add_argument("table_name", help="Name of the table to create")
    parser.add_argument("columns", help='Column definitions: "name type [PK] [FK:ref] [constraints], ..."')
    parser.add_argument("--output", default=".", help="Output directory (default: current dir)")
    args = parser.parse_args()

    if not re.match(r"^[a-z_][a-z0-9_]*$", args.table_name):
        print("Error: Table name must be lowercase snake_case.", file=sys.stderr)
        sys.exit(1)

    sql = generate_sql(args.table_name, args.columns)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_create_{args.table_name}.sql"

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    output_path.write_text(sql, encoding="utf-8")
    print(f"Migration written to: {output_path}")


if __name__ == "__main__":
    main()
