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

The parser targets PostgreSQL DDL (which is also what Supabase speaks). It is
deliberately a structural reader, not a full SQL grammar: it extracts tables,
columns, types, nullability, keys, foreign keys and enums, and ignores anything
it does not recognise rather than guessing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from eng_common import now_iso

# `CREATE TABLE [IF NOT EXISTS] [schema.]name (` up to its matching paren.
_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>[\"\w.]+)\s*\(",
    re.IGNORECASE,
)
_CREATE_ENUM = re.compile(
    r"CREATE\s+TYPE\s+(?P<name>[\"\w.]+)\s+AS\s+ENUM\s*\((?P<values>[^)]*)\)",
    re.IGNORECASE,
)
_CREATE_INDEX = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?P<name>[\"\w.]+)\s+ON\s+(?P<table>[\"\w.]+)\s*(?:USING\s+\w+\s*)?\((?P<columns>[^)]*)\)",
    re.IGNORECASE,
)
_ENABLE_RLS = re.compile(
    r"ALTER\s+TABLE\s+(?P<table>[\"\w.]+)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE,
)
_CREATE_POLICY = re.compile(
    r"CREATE\s+POLICY\s+(?P<name>\"[^\"]+\"|\S+)\s+ON\s+(?P<table>[\"\w.]+)",
    re.IGNORECASE,
)
_REFERENCES = re.compile(
    r"REFERENCES\s+(?P<table>[\"\w.]+)\s*(?:\(\s*(?P<column>[\"\w]+)\s*\))?",
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


def _clean(identifier: str) -> str:
    return identifier.strip().strip('"').strip()


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


def _parse_column(clause: str) -> dict[str, Any] | None:
    tokens = clause.split()
    if len(tokens) < 2:
        return None
    name = _clean(tokens[0])
    upper = clause.upper()
    # Type is everything up to the first constraint keyword.
    type_tokens: list[str] = []
    for token in tokens[1:]:
        if token.upper().rstrip(",").strip("(") in {
            "PRIMARY",
            "NOT",
            "NULL",
            "UNIQUE",
            "REFERENCES",
            "DEFAULT",
            "CHECK",
            "GENERATED",
            "CONSTRAINT",
            "COLLATE",
        }:
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


def parse_schema_sql(sql: str) -> dict[str, Any]:
    """Structure a PostgreSQL DDL file into entities, relationships and enums."""
    sql = _strip_comments(sql)
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []

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
            column = _parse_column(clause)
            if not column:
                continue
            columns.append(column)
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
        "dialect": "postgresql",
        "enums": enums,
        "entities": sorted(entities, key=lambda item: item["name"]),
        "relationships": sorted(relationships, key=lambda item: (item["from"], item["from_column"])),
        "warnings": _model_warnings(entities),
    }


def _model_warnings(entities: list[dict[str, Any]]) -> list[str]:
    """Structural problems worth surfacing before they reach a migration."""
    warnings: list[str] = []
    for entity in entities:
        if not entity["primary_key"]:
            warnings.append(f"{entity['name']}: no primary key")
        if entity["columns"] and not entity["rls_enabled"]:
            warnings.append(f"{entity['name']}: row level security not enabled")
        sensitive = [column["name"] for column in entity["columns"] if column.get("sensitive_hint")]
        if sensitive:
            warnings.append(
                f"{entity['name']}: confirm handling of possibly sensitive column(s): {', '.join(sensitive)}"
            )
    return warnings


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


def find_live_schema_sources(root: Path) -> list[Path]:
    """Migration and schema files that represent what is actually deployed."""
    candidates: list[Path] = []
    for pattern in (
        "supabase/migrations/*.sql",
        "migrations/*.sql",
        "db/migrate/*.sql",
        "prisma/schema.prisma",
        "drizzle/*.sql",
    ):
        candidates.extend(sorted(root.glob(pattern)))
    return candidates


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
