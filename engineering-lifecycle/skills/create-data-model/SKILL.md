---
name: create-data-model
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*), Bash(bash:*)
description: Use to design the database schema after the PRD, technical design document, and architecture plan are agreed. Produces a durable schema file plus a generated JSON model, ERD, and migrations that later backend work reads back. Works on PostgreSQL, MySQL, SQLite, SQL Server and MongoDB. Use for entities, relationships, ownership, sensitive data, retention, indexes, access control, and migration risk.
argument-hint: "[--initiative <id>] [--dialect postgresql|mysql|sqlite|sqlserver|mongodb] [--introspect] [--regenerate]"
---

# Create Data Model

## Trigger

Use when the user asks for entities, database schema, ERD, storage boundaries,
data lifecycle, migrations, indexes, row level security, collections, or data
ownership — on any supported database.

## When To Use

- After the PRD, technical design document, and architecture plan are agreed and
  handed over. The schema is downstream of those, not a substitute for them.
- Before API contracts, and before any persistence-heavy implementation.
- When an existing backend has grown without a recorded model and needs one.

## Why This Skill Produces Files, Not Prose

An entity list written as Markdown cannot be read back by anything. Later backend
work then re-derives the model from whatever code is nearby, and the schema drifts
one query at a time. That is the usual cause of a messy backend.

So the deliverable is a real schema file. `schema.sql` is the **source of truth**:
a human writes and edits it, and it is what ships. Everything else in `data/` is
generated from it and must never be hand-edited. On a document store the same role
is played by `schema.json`.

## Dialects

This skill is not Postgres-only. The dialect decides whether enums are a declared
type, whether row level security exists, how identifiers are quoted, and what a
migration is allowed to say — so it is resolved **first**, before any design work.

Supported: `postgresql` (and Supabase), `mysql` (and MariaDB), `sqlite`,
`sqlserver`, `mongodb`. See `references/data-model-adapters.md` for what each one
changes.

## Inputs Inspected

- `prd.md`, `technical-design-document.md` and `system-map/` from the same
  initiative under `.project/docs/engineering/<initiative-id>/`.
- `context/stack.json` for the detected **database** and backend. This decides the
  dialect unless `--dialect` overrides it.
- Existing schema, migrations, ORM models, and storage config in the repo
  (`migrations/`, `supabase/migrations/`, `prisma/schema.prisma`, `drizzle/`).
- Any existing `data/schema.sql` or `data/schema.json` for this initiative.

## Workflow

1. **Confirm the initiative.** Resolve the active initiative. If the request does
   not clearly belong to it, ask before writing.
2. **Resolve the dialect, and say which one.** Read the database from
   `context/stack.json`, or take `--dialect`. State it and the reason before
   designing anything:

   > Modelling in **MySQL** (from `context/stack.json` database: MySQL).

   If no database is detected and none was given, ask rather than defaulting
   silently — the answer changes the schema, not just its formatting. An ORM in the
   stack does not settle it: Prisma, Drizzle and TypeORM all run on several
   engines. Read `references/data-model-adapters.md` for the dialect you land on.
3. **Read the upstream artifacts.** The entities come from the PRD's functional
   requirements and the technical design document, not from imagination. If those
   do not exist, say so and offer to create them first rather than guessing.
4. **Introspect what already exists.** For a repo with a live database, run:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/schema-introspect.sh"
   ```

   It reads `DATABASE_URL` (engine-specific aliases such as `SUPABASE_DB_URL`,
   `MYSQL_URL` and `MONGODB_URI` also work) and picks the client for the resolved
   dialect. Pass `--dialect` to force one. Never propose a greenfield schema over
   an existing one without reconciling.
5. **Design the schema.** Work through, in order: enums and types, tables in
   dependency order, constraints, indexes for the real query patterns, access
   control, then triggers. Normalise to third normal form unless there is a stated
   reason not to, and record the reason when there is.

   Access control is where dialects diverge most. Postgres and SQL Server have row
   level security; MySQL and SQLite do not, and pretending otherwise produces a
   migration that will not run. Use what the adapter says the engine actually has.
6. **Write the schema file.** `data/schema.sql` for a SQL engine —
   one file, idempotent where the dialect supports it, commented by section. For a
   document store, `data/schema.json` with collections and fields. For a single new
   table the generator gives a correct starting point in the right dialect:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/generate-migration.py" orders \
     "id uuid PK, user_id uuid FK:users.id, total numeric NOT NULL" \
     --output .project/docs/engineering/<initiative-id>/data/migrations
   ```

7. **Generate the sidecar and diagram.** Never hand-write these:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/schema-to-json.py" --initiative <initiative-id>
   ```

   Check the `dialect` and `dialect_reason` it echoes back — if they are wrong, the
   model is wrong. Then read the `warnings`. Missing primary keys and
   possibly-sensitive columns are reported for a decision, not silently accepted.
   Row-level-security warnings appear only for engines that have it.
8. **Write the narrative.** `data/entity-model.md` covers what the schema cannot
   express: source of truth, ownership boundaries, sensitivity classification,
   retention and deletion, audit needs, import/export paths, and migration risk.
   On a document store, also record embedding-versus-referencing decisions and
   which references are modelling intent rather than enforced constraints.
9. **Check drift** against what actually shipped:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/schema-drift-check.py"
   ```

10. **Convene the council** via `run-engineering-council` before any irreversible
    or high-blast-radius migration.
11. **Validate:**

    ```bash
    python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" <artifact paths>
    ```

## Arguments

| Flag | Effect |
| --- | --- |
| `--initiative <id>` | Target a specific initiative instead of the active one. |
| `--dialect <name>` | Force the database dialect instead of using the detected one. |
| `--introspect` | Start from the live database rather than a blank schema. |
| `--regenerate` | Re-derive `data-model.json` and `erd.mmd` from the schema file and stop. |

## Outputs

| Path | Owner | Role |
| --- | --- | --- |
| `data/schema.sql` | **human** | Source of truth on a SQL engine. Full DDL. |
| `data/schema.json` | **human** | Source of truth on a document store. Collections and fields. |
| `data/data-model.json` | generated | Machine-readable sidecar. What hooks and the ledger read. |
| `data/erd.mmd` | generated | Mermaid ERD. |
| `data/entity-model.md` | human | Ownership, sensitivity, retention, audit, migration risk. |
| `data/migrations/*.sql` | human | Incremental changes once the schema is in use. |

All under `.project/docs/engineering/<initiative-id>/`.

## How The Model Gets Used Later

Writing the schema is only half the job. Once `data-model.json` exists, a
`PreToolUse` hook injects the entity and relationship list into any edit touching
backend, migration, schema or ORM files, and escalates to a confirmation prompt
when an edit introduces a table the model does not contain. A `PostToolUse` check
reports divergence between the model and shipped migrations.

That is what stops the schema from being designed once and then ignored.

## Required Sections

`entity-model.md` must contain:

- Entities
- Relationships
- Ownership
- Sensitivity
- Retention
- Audit And Lifecycle
- Migration Risk
- Open Questions

## Safety Constraints

- Never hand-edit `data-model.json` or `erd.mmd`. Edit the schema file and regenerate.
- Do not propose destructive migrations without explicit risk and rollback notes.
- Every table a client can reach needs a stated access-control decision, in the
  form the engine actually offers. On Postgres and SQL Server that is row level
  security — enable it on those tables and write the policies, since RLS enabled
  with no policy denies everything, which is safe but not finished. On MySQL,
  SQLite and MongoDB there is no such mechanism: say how access is restricted
  instead of leaving the question unanswered, and never emit RLS statements that
  cannot run.
- Mark sensitive fields and retention assumptions. The generated `sensitive_hint`
  flags are prompts for a human decision, not a classification.
- Never put real credentials or connection strings in any artifact.
- Record unresolved source-of-truth questions under Open Questions; they are
  scraped into the open-questions store automatically.

## Related Agents

- `domain-modeller`
- `database-engineer`
- `security-reviewer`
