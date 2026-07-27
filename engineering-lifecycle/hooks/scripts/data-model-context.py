#!/usr/bin/env python3
"""PreToolUse: put the data model in front of backend and migration edits.

Designing a schema once and filing it away does not stop a backend becoming a
mess. The model has to be present at the moment someone writes a query, a
migration, or a model class, or it gets re-invented on the spot.

This fires on edits to backend, migration, schema and ORM files, injects the
entity and relationship list, and escalates to `ask` when the edit looks like it
introduces a table the model does not know about.

Dormant when there is no workspace or no data model, and silent for files that
are not backend work, so it never becomes noise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from data_model import summarize
from eng_common import (
    classify_file_path,
    docs_root,
    emit_json,
    hook_additional_context,
    load_hook_payload,
    permission_output,
    read_json,
    relpath,
    repo_root,
    workspace_exists,
)

# Extensions where a data access layer plausibly lives.
_BACKEND_SUFFIXES = {".sql", ".py", ".ts", ".js", ".go", ".rb", ".php", ".rs", ".java", ".kt", ".prisma"}
_BACKEND_HINTS = ("migration", "schema", "model", "entity", "repository", "dao", "query", "db", "database", "prisma")
_CREATE_TABLE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\"\w.]+)", re.IGNORECASE)
_ADD_COLUMN = re.compile(r"ALTER\s+TABLE\s+([\"\w.]+)\s+ADD\s+COLUMN", re.IGNORECASE)


def is_backend_target(path: str) -> bool:
    lowered = path.lower().replace("\\", "/")
    if Path(lowered).suffix not in _BACKEND_SUFFIXES:
        return False
    if classify_file_path(Path(lowered)) in {"migration", "schema"}:
        return True
    return any(hint in lowered for hint in _BACKEND_HINTS)


def load_models(root: Path) -> list[tuple[str, dict]]:
    base = docs_root(root)
    if not base.is_dir():
        return []
    found = []
    for path in sorted(base.glob("*/data/data-model.json")):
        model = read_json(path)
        if model and model.get("entities"):
            found.append((relpath(path, root), model))
    return found


def new_tables(text: str, known: set[str]) -> list[str]:
    proposed = {name.strip('"').split(".")[-1].lower() for name in _CREATE_TABLE.findall(text)}
    proposed |= {name.strip('"').split(".")[-1].lower() for name in _ADD_COLUMN.findall(text)}
    return sorted(proposed - known)


def main() -> int:
    payload = load_hook_payload()
    root = repo_root()
    if not payload or not workspace_exists(root):
        return 0

    tool_input = payload.get("tool_input") or {}
    target = str(tool_input.get("file_path") or tool_input.get("path") or "")
    if not target or not is_backend_target(target):
        return 0

    models = load_models(root)
    if not models:
        return 0

    known = {entity["name"].split(".")[-1].lower() for _, model in models for entity in model["entities"]}
    content = " ".join(
        str(tool_input.get(key) or "") for key in ("content", "new_string", "new_str", "replace_all_with")
    )
    unknown = new_tables(content, known) if content else []

    source = models[0][1].get("source", "data/schema.sql")
    body = "\n\n".join(f"From {path}:\n{summarize(model)}" for path, model in models)

    if unknown:
        emit_json(
            permission_output(
                "PreToolUse",
                "ask",
                f"This edit introduces table(s) the data model does not contain: {', '.join(unknown)}. "
                f"Update {source} and regenerate the model first, or confirm this is intentional.",
            )
        )
        return 0

    emit_json(
        hook_additional_context(
            "PreToolUse",
            f"Backend edit detected. Conform to the existing data model rather than inventing entities.\n"
            f"Source of truth: {source} (edit it, then run scripts/schema-to-json.py to regenerate).\n\n{body}",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
