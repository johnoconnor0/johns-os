#!/usr/bin/env python3
"""Generate data-model.json and erd.mmd from an initiative's schema.sql.

`schema.sql` is authored and owned by a human. Everything this writes is derived
from it, so the sidecar and the diagram can never drift from the schema they
describe.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from data_model import parse_schema_sql, render_erd
from eng_common import docs_root, emit_json, relpath, repo_root, write_json, write_text


def initiative_data_dir(root: Path, initiative: str) -> Path:
    return docs_root(root) / initiative / "data"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--initiative", default="", help="Initiative id. Defaults to the active one.")
    parser.add_argument("--schema", default="", help="Path to schema.sql. Overrides --initiative.")
    parser.add_argument("--no-erd", action="store_true", help="Skip regenerating erd.mmd")
    args = parser.parse_args()

    root = repo_root(Path(args.root))
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
        schema = out_dir / "schema.sql"

    if not schema.is_file():
        emit_json({"error": f"schema not found: {relpath(schema, root)}"})
        return 1

    model = parse_schema_sql(schema.read_text(encoding="utf-8"))
    model["source"] = relpath(schema, root)
    written = [relpath(out_dir / "data-model.json", root)]
    write_json(out_dir / "data-model.json", model)
    if not args.no_erd:
        write_text(out_dir / "erd.mmd", render_erd(model))
        written.append(relpath(out_dir / "erd.mmd", root))

    emit_json(
        {
            "source": model["source"],
            "written": written,
            "entity_count": len(model["entities"]),
            "relationship_count": len(model["relationships"]),
            "warnings": model["warnings"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
