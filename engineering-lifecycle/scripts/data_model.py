#!/usr/bin/env python3
"""Turn a hand-written ``schema.sql`` into a machine-readable data model.

The data model used to be Markdown prose plus a nine-line Mermaid sketch. Nothing
downstream could read it, so later backend work had no durable answer to "what
entities exist and how do they relate?" and invented its own each time. That is
what makes a backend drift into a mess.

`schema.sql` is the source of truth: a human writes and edits it, and it is the
thing that actually ships. `data-model.json` is generated from it, and is what
hooks, the ledger and the ERD read. Generating the sidecar rather than
hand-maintaining it means the two can never disagree.

The parser is deliberately a structural reader, not a full SQL grammar: it extracts
tables, columns, types, nullability, keys, foreign keys and enums, and ignores
anything it does not recognise rather than guessing.

It reads whichever dialect it is given (see `dialects.py`). It used to read only
PostgreSQL and stamp `"dialect": "postgresql"` on the result whatever the repo
actually ran, so a MySQL project got a model that was wrong about its identifiers,
its enums, and — every table, every run — its row level security.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from dialects import DEFAULT_DIALECT, Dialect, get_dialect
from eng_common import now_iso

# Identifiers may be bare, "quoted", `backticked` (MySQL) or [bracketed] (SQL
# Server). One character class covers every dialect; `_clean` strips whatever
# wrapper was actually used.
_IDENT = r"[\"`\[\]\w.]+"

# `CREATE TABLE [IF NOT EXISTS] [schema.]name (` up to its matching paren.
_CREATE_TABLE = re.compile(
    rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>{_IDENT})\s*\(",
    re.IGNORECASE,
)
_CREATE_ENUM = re.compile(
    rf"CREATE\s+TYPE\s+(?P<name>{_IDENT})\s+AS\s+ENUM\s*\((?P<values>[^)]*)\)",
    re.IGNORECASE,
)
# MySQL writes its enums as a column type rather than declaring them.
_INLINE_ENUM = re.compile(r"^\s*ENUM\s*\((?P<values>.*)\)\s*$", re.IGNORECASE | re.DOTALL)
_CREATE_INDEX = re.compile(
    rf"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?"
    rf"(?P<name>{_IDENT})\s+ON\s+(?P<table>{_IDENT})\s*(?:USING\s+\w+\s*)?\((?P<columns>[^)]*)\)",
    re.IGNORECASE,
)
_ENABLE_RLS = re.compile(
    rf"ALTER\s+TABLE\s+(?P<table>{_IDENT})\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE,
)
_CREATE_POLICY = re.compile(
    rf"CREATE\s+POLICY\s+(?P<name>\"[^\"]+\"|\S+)\s+ON\s+(?P<table>{_IDENT})",
    re.IGNORECASE,
)
_REFERENCES = re.compile(
    rf"REFERENCES\s+(?P<table>{_IDENT})\s*(?:\(\s*(?P<column>[\"`\[\]\w]+)\s*\))?",
    re.IGNORECASE,
)
_TABLE_CONSTRAINT = re.compile(
    r"^\s*(?:CONSTRAINT\s+\S+\s+)?(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|EXCLUDE)\b",
    re.IGNORECASE,
)
_COLUMN_LIST = re.compile(r"\(\s*([^)]*?)\s*\)")

# Column names that conventionally carry personal or otherwise sensitive data.
# A hint for the human to confirm, never a classification claimed as fact.
_SENSITIVE_HINTS = (
    "email",
    "phone",
    "password",
    "token",
    "secret",
    "ssn",
    "tax",
    "dob",
    "birth",
    "address",
    "ip_address",
    "card",
    "iban",
    "passport",
    "licence",
    "license",
)


_QUOTE_CHARS = re.compile(r"[\"`\[\]]")


def _clean(identifier: str) -> str:
    """Remove whichever quoting a dialect used around an identifier.

    Removing rather than stripping the ends, because a schema-qualified name quotes
    each part separately: `[dbo].[Orders]` must become `dbo.Orders`, not `dbo].[Orders`.
    """
    return _QUOTE_CHARS.sub("", identifier).strip()


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


def _balanced_body(sql: str, open_index: int) -> tuple[str, int]:
    """Text between `sql[open_index]` ('(') and its matching ')'."""
    depth = 0
    for index in range(open_index, len(sql)):
        char = sql[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return sql[open_index + 1 : index], index
    return sql[open_index + 1 :], len(sql)


def _split_top_level(body: str) -> list[str]:
    """Split a table body on commas that are not inside parentheses or quotes."""
    parts: list[str] = []
    depth = 0
    quote: str | None = None
    current: list[str] = []
    for char in body:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in "'\"":
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def _parse_column(clause: str, dialect: Dialect = DEFAULT_DIALECT) -> dict[str, Any] | None:
    tokens = clause.split()
    if len(tokens) < 2:
        return None
    name = _clean(tokens[0])
    upper = clause.upper()
    # Type is everything up to the first constraint keyword. Which words count as a
    # constraint is dialect-specific: without MySQL's AUTO_INCREMENT in the set,
    # `id BIGINT AUTO_INCREMENT PRIMARY KEY` yields the type "BIGINT AUTO_INCREMENT".
    keywords = dialect.column_keywords
    type_tokens: list[str] = []
    for token in tokens[1:]:
        if token.upper().rstrip(",").split("(")[0] in keywords:
            break
        type_tokens.append(token)
    column: dict[str, Any] = {
        "name": name,
        "type": " ".join(type_tokens).strip().rstrip(",") or "unknown",
        "nullable": "NOT NULL" not in upper and "PRIMARY KEY" not in upper,
        "primary_key": "PRIMARY KEY" in upper,
        "unique": "UNIQUE" in upper,
    }
    default = re.search(r"DEFAULT\s+(.+?)(?:\s+(?:NOT\s+NULL|UNIQUE|REFERENCES|CHECK)|$)", clause, re.IGNORECASE)
    if default:
        column["default"] = default.group(1).strip().rstrip(",")
    reference = _REFERENCES.search(clause)
    if reference:
        column["references"] = {
            "table": _clean(reference.group("table")),
            "column": _clean(reference.group("column") or "id"),
        }
    lowered = name.lower()
    if any(hint in lowered for hint in _SENSITIVE_HINTS):
        column["sensitive_hint"] = True
    return column


def parse_schema_sql(sql: str, dialect: Dialect | str | None = None) -> dict[str, Any]:
    """Structure a SQL DDL file into entities, relationships and enums.

    `dialect` decides how identifiers are unquoted, which keywords end a column
    type, where enums come from, and whether row level security means anything.
    """
    dialect = dialect if isinstance(dialect, Dialect) else get_dialect(dialect)
    if not dialect.sql:
        raise ValueError(
            f"{dialect.label} is a document store with no DDL to parse. "
            f"Author the model as schema.json and use parse_document_model()."
        )
    sql = _strip_comments(sql)
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    enums: list[dict[str, Any]] = []

    if dialect.declared_enums:
        enums = [
            {
                "name": _clean(match.group("name")),
                "values": [value.strip().strip("'\"") for value in match.group("values").split(",") if value.strip()],
            }
            for match in _CREATE_ENUM.finditer(sql)
        ]

    for match in _CREATE_TABLE.finditer(sql):
        table = _clean(match.group("name"))
        body, _ = _balanced_body(sql, match.end() - 1)
        columns: list[dict[str, Any]] = []
        primary_key: list[str] = []
        uniques: list[list[str]] = []

        for clause in _split_top_level(body):
            constraint = _TABLE_CONSTRAINT.match(clause)
            if constraint:
                kind = re.sub(r"\s+", " ", constraint.group(1).upper())
                listed = _COLUMN_LIST.search(clause)
                names = [_clean(item) for item in listed.group(1).split(",")] if listed else []
                if kind == "PRIMARY KEY":
                    primary_key = names
                elif kind == "UNIQUE":
                    uniques.append(names)
                elif kind == "FOREIGN KEY":
                    reference = _REFERENCES.search(clause)
                    if reference and names:
                        relationships.append(
                            {
                                "from": table,
                                "from_column": names[0],
                                "to": _clean(reference.group("table")),
                                "to_column": _clean(reference.group("column") or "id"),
                                "cardinality": "many-to-one",
                            }
                        )
                continue
            column = _parse_column(clause, dialect)
            if not column:
                continue
            columns.append(column)
            if dialect.inline_enums:
                inline = _INLINE_ENUM.match(column["type"])
                if inline:
                    enums.append(
                        {
                            "name": f"{table}.{column['name']}",
                            "values": [
                                value.strip().strip("'\"")
                                for value in _split_top_level(inline.group("values"))
                                if value.strip()
                            ],
                            "inline": True,
                        }
                    )
            if column["primary_key"]:
                primary_key.append(column["name"])
            if "references" in column:
                relationships.append(
                    {
                        "from": table,
                        "from_column": column["name"],
                        "to": column["references"]["table"],
                        "to_column": column["references"]["column"],
                        "cardinality": "one-to-one" if column["unique"] else "many-to-one",
                    }
                )

        entities.append(
            {
                "name": table,
                "columns": columns,
                "primary_key": primary_key,
                "unique_constraints": uniques,
                "indexes": [],
                "rls_enabled": False,
                "policies": [],
            }
        )

    by_name = {entity["name"]: entity for entity in entities}
    for match in _CREATE_INDEX.finditer(sql):
        entity = by_name.get(_clean(match.group("table")))
        if entity is not None:
            entity["indexes"].append(
                {
                    "name": _clean(match.group("name")),
                    "columns": [_clean(item) for item in match.group("columns").split(",")],
                }
            )
    # Only Postgres spells row level security this way. Parsing it unconditionally
    # was harmless; warning about its absence on engines that have no such feature
    # was not — it produced one dead warning per table on every MySQL and SQLite
    # model, which is how a warnings list stops being read.
    if dialect.supports_row_level_security:
        for match in _ENABLE_RLS.finditer(sql):
            entity = by_name.get(_clean(match.group("table")))
            if entity is not None:
                entity["rls_enabled"] = True
        for match in _CREATE_POLICY.finditer(sql):
            entity = by_name.get(_clean(match.group("table")))
            if entity is not None:
                entity["policies"].append(_clean(match.group("name")))

    return {
        "generated_at": now_iso(),
        "dialect": dialect.name,
        "enums": enums,
        "entities": sorted(entities, key=lambda item: item["name"]),
        "relationships": sorted(relationships, key=lambda item: (item["from"], item["from_column"])),
        "warnings": _model_warnings(entities, dialect),
    }


def _model_warnings(entities: list[dict[str, Any]], dialect: Dialect = DEFAULT_DIALECT) -> list[str]:
    """Structural problems worth surfacing before they reach a migration."""
    warnings: list[str] = []
    for entity in entities:
        if not entity["primary_key"]:
            warnings.append(f"{entity['name']}: no primary key")
        if dialect.supports_row_level_security and entity["columns"] and not entity["rls_enabled"]:
            warnings.append(f"{entity['name']}: row level security not enabled")
        sensitive = [column["name"] for column in entity["columns"] if column.get("sensitive_hint")]
        if sensitive:
            warnings.append(
                f"{entity['name']}: confirm handling of possibly sensitive column(s): {', '.join(sensitive)}"
            )
    return warnings


def parse_document_model(text: str) -> dict[str, Any]:
    """Structure a `schema.json` collection spec into the same model shape.

    A document store has no DDL, so the alternative to modelling it badly as SQL is
    a small explicit format: collections, their fields, and which fields point at
    another collection. Everything downstream — the ERD, the backend context hook,
    the drift check — reads the shared shape and does not care which produced it.

        {"collections": [
          {"name": "users", "fields": [
            {"name": "_id", "type": "objectId", "primary_key": true},
            {"name": "org_id", "type": "objectId", "references": {"table": "orgs", "column": "_id"}}]}]}
    """
    data = json.loads(text)
    collections = data.get("collections")
    if not isinstance(collections, list):
        raise ValueError("schema.json must contain a top-level 'collections' array")

    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    for collection in collections:
        name = str(collection.get("name", "")).strip()
        if not name:
            continue
        columns: list[dict[str, Any]] = []
        primary_key: list[str] = []
        for raw in collection.get("fields", []) or []:
            field_name = str(raw.get("name", "")).strip()
            if not field_name:
                continue
            column: dict[str, Any] = {
                "name": field_name,
                "type": str(raw.get("type", "unknown")),
                "nullable": not bool(raw.get("required", False)) and not bool(raw.get("primary_key", False)),
                "primary_key": bool(raw.get("primary_key", False)),
                "unique": bool(raw.get("unique", False)),
            }
            reference = raw.get("references")
            if isinstance(reference, dict) and reference.get("table"):
                column["references"] = {
                    "table": str(reference["table"]),
                    "column": str(reference.get("column", "_id")),
                }
                relationships.append(
                    {
                        "from": name,
                        "from_column": field_name,
                        "to": column["references"]["table"],
                        "to_column": column["references"]["column"],
                        "cardinality": "one-to-one" if column["unique"] else "many-to-one",
                    }
                )
            if any(hint in field_name.lower() for hint in _SENSITIVE_HINTS):
                column["sensitive_hint"] = True
            columns.append(column)
            if column["primary_key"]:
                primary_key.append(field_name)
        entities.append(
            {
                "name": name,
                "columns": columns,
                "primary_key": primary_key,
                "unique_constraints": [],
                "indexes": [
                    {"name": str(index.get("name", "")), "columns": list(index.get("columns", []))}
                    for index in collection.get("indexes", []) or []
                ],
                "rls_enabled": False,
                "policies": [],
            }
        )

    return {
        "generated_at": now_iso(),
        "dialect": "mongodb",
        "enums": [],
        "entities": sorted(entities, key=lambda item: item["name"]),
        "relationships": sorted(relationships, key=lambda item: (item["from"], item["from_column"])),
        "warnings": _model_warnings(entities, get_dialect("mongodb")),
    }


def render_erd(model: dict[str, Any]) -> str:
    """Mermaid ERD generated from the model, never hand-drawn.

    A hand-drawn diagram is out of date the moment the schema changes, which is
    why the previous nine-line erd.mmd told nobody anything useful.
    """
    lines = ["erDiagram"]
    for entity in model.get("entities", []):
        lines.append(f"  {entity['name']} {{")
        for column in entity["columns"]:
            kind = re.sub(r"[^A-Za-z0-9_]", "_", column["type"].split("(")[0].strip()) or "unknown"
            marker = " PK" if column["name"] in entity["primary_key"] else ""
            lines.append(f"    {kind} {column['name']}{marker}")
        lines.append("  }")
    for relationship in model.get("relationships", []):
        symbol = "||--||" if relationship["cardinality"] == "one-to-one" else "}o--||"
        lines.append(f"  {relationship['from']} {symbol} {relationship['to']} : {relationship['from_column']}")
    return "\n".join(lines) + "\n"


def summarize(model: dict[str, Any], max_entities: int = 40) -> str:
    """A compact description for injecting into a backend editing session."""
    entities = model.get("entities", [])
    if not entities:
        return ""
    lines = [f"Data model: {len(entities)} entities."]
    for entity in entities[:max_entities]:
        keys = ", ".join(entity["primary_key"]) or "no PK"
        columns = ", ".join(f"{column['name']}:{column['type']}" for column in entity["columns"][:12])
        lines.append(f"  - {entity['name']} (pk {keys}): {columns}")
    if len(entities) > max_entities:
        lines.append(f"  ... and {len(entities) - max_entities} more")
    relationships = model.get("relationships", [])
    if relationships:
        lines.append("Relationships:")
        for relationship in relationships[:max_entities]:
            lines.append(
                f"  - {relationship['from']}.{relationship['from_column']} -> "
                f"{relationship['to']}.{relationship['to_column']} ({relationship['cardinality']})"
            )
    return "\n".join(lines)


def find_live_schema_sources(root: Path, dialect: Dialect | str | None = None) -> list[Path]:
    """Migration and schema files that represent what is actually deployed.

    ORM schemas are searched for every dialect — Prisma and Drizzle run on all of
    them — while the migration directories come from the adapter, so a Mongo repo
    is not scanned for `supabase/migrations`.
    """
    dialect = dialect if isinstance(dialect, Dialect) else get_dialect(dialect)
    patterns = [*dialect.migration_sources, "prisma/schema.prisma", "drizzle/*.sql"]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(sorted(root.glob(pattern)))
    return sorted(set(candidates))


def drift_report(model: dict[str, Any], sources: list[Path], root: Path) -> dict[str, Any]:
    """Entities in the model but absent from live migrations, and vice versa.

    Name-level only, deliberately. A column-level diff across dialects would need
    a real migration engine; a missing or unexpected table is the divergence that
    actually bites, and reporting only what can be established keeps the signal
    trustworthy.
    """
    modelled = {entity["name"].split(".")[-1].lower() for entity in model.get("entities", [])}
    live: set[str] = set()
    for path in sources:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if path.suffix == ".prisma":
            live |= {name.lower() for name in re.findall(r"^model\s+(\w+)", text, re.MULTILINE)}
        else:
            live |= {_clean(match.group("name")).split(".")[-1].lower() for match in _CREATE_TABLE.finditer(text)}
    return {
        "sources": [path.relative_to(root).as_posix() for path in sources],
        "modelled_only": sorted(modelled - live) if live else [],
        "live_only": sorted(live - modelled),
        "in_sync": bool(live) and not (modelled - live) and not (live - modelled),
        "checked": bool(live),
    }
