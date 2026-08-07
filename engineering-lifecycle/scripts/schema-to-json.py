#!/usr/bin/env python3
"""Generate data-model.json and erd.mmd from an initiative's schema file.

The schema is authored and owned by a human. Everything this writes is derived
from it, so the sidecar and the diagram can never drift from the schema they
describe.

The dialect comes from the database `detect-stack` found, or from `--dialect`.
SQL engines are read from `schema.sql`; a document store from `schema.json`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from data_model import parse_document_model, parse_schema_sql, render_erd
from dialects import DIALECTS, model_filename, resolve_dialect
from eng_common import docs_root, emit_json, relpath, resolve_cli_root, write_json, write_text


def initiative_data_dir(root: Path, initiative: str) -> Path:
    return docs_root(root) / initiative / "data"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--initiative", default="", help="Initiative id. Defaults to the active one.")
    parser.add_argument("--schema", default="", help="Path to the schema file. Overrides --initiative.")
    parser.add_argument(
        "--dialect",
        default="",
        choices=["", *sorted(DIALECTS)],
        help="Database dialect. Defaults to the database detected in context/stack.json.",
    )
    parser.add_argument("--no-erd", action="store_true", help="Skip regenerating erd.mmd")
    args = parser.parse_args()

    root = resolve_cli_root(args.root).root
    dialect, reason = resolve_dialect(root, args.dialect)
    if args.schema:
        schema = Path(args.schema)
        schema = schema if schema.is_absolute() else root / schema
        out_dir = schema.parent
    else:
        initiative = args.initiative
        if not initiative:
            from quality_tools import load_initiative_registry

            initiative = load_initiative_registry(root)["active"] or ""
        if not initiative:
            emit_json({"error": "no active initiative; pass --initiative or --schema"})
            return 1
        out_dir = initiative_data_dir(root, initiative)
        schema = out_dir / model_filename(dialect)

    if not schema.is_file():
        emit_json(
            {
                "error": f"schema not found: {relpath(schema, root)}",
                "dialect": dialect.name,
                "dialect_reason": reason,
                "expected_filename": model_filename(dialect),
            }
        )
        return 1

    text = schema.read_text(encoding="utf-8")
    # A document store has no DDL. Reading its collection spec through the SQL
    # parser is what used to produce an empty model stamped "postgresql".
    model = parse_schema_sql(text, dialect) if dialect.sql else parse_document_model(text)
    model["source"] = relpath(schema, root)
    model["dialect_reason"] = reason
    written = [relpath(out_dir / "data-model.json", root)]
    write_json(out_dir / "data-model.json", model)
    if not args.no_erd:
        write_text(out_dir / "erd.mmd", render_erd(model))
        written.append(relpath(out_dir / "erd.mmd", root))

    emit_json(
        {
            "source": model["source"],
            "dialect": model["dialect"],
            "dialect_reason": reason,
            "written": written,
            "entity_count": len(model["entities"]),
            "relationship_count": len(model["relationships"]),
            "warnings": model["warnings"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
