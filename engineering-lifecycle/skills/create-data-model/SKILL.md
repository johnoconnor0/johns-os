---
name: create-data-model
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*), Bash(bash:*)
description: Use to design the database schema after the PRD, technical design document, and architecture plan are agreed. Produces a durable schema.sql plus a generated JSON model, ERD, and migrations that later backend work reads back. Use for entities, relationships, ownership, sensitive data, retention, indexes, RLS, and migration risk.
argument-hint: "[--initiative <id>] [--introspect] [--regenerate]"
---

# Create Data Model

## Trigger

Use when the user asks for entities, database schema, ERD, storage boundaries,
data lifecycle, migrations, indexes, row level security, or data ownership.

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
generated from it and must never be hand-edited.

## Inputs Inspected

- `prd.md`, `technical-design-document.md` and `system-map/` from the same
  initiative under `.project/docs/engineering/<initiative-id>/`.
- `context/stack.json` for the detected database and backend.
- Existing schema, migrations, ORM models, and storage config in the repo
  (`supabase/migrations/`, `prisma/schema.prisma`, `drizzle/`, `migrations/`).
- Any existing `data/schema.sql` for this initiative.

## Workflow

1. **Confirm the initiative.** Resolve the active initiative. If the request does
   not clearly belong to it, ask before writing.
2. **Read the upstream artifacts.** The entities come from the PRD's functional
   requirements and the technical design document, not from imagination. If those
   do not exist, say so and offer to create them first rather than guessing.
3. **Introspect what already exists.** For a repo with a live database, run:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/schema-introspect.sh"
   ```

   Never propose a greenfield schema over an existing one without reconciling.
4. **Design the schema.** Work through, in order: enums and types, tables in
   dependency order, constraints, indexes for the real query patterns, RLS
   policies, then triggers. Normalise to third normal form unless there is a
   stated reason not to, and record the reason when there is.
5. **Write `data/schema.sql`.** One file, idempotent where possible
   (`CREATE TABLE IF NOT EXISTS`), commented by section. For a single new table
   the generator gives a correct starting point:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/generate-migration.py" orders \
     "id uuid PK, user_id uuid FK:users.id, total numeric NOT NULL" \
     --output .project/docs/engineering/<initiative-id>/data/migrations
   ```

6. **Generate the sidecar and diagram.** Never hand-write these:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/schema-to-json.py" --initiative <initiative-id>
   ```

   Read the `warnings` it returns. Missing primary keys, tables without RLS, and
   possibly-sensitive columns are reported for a decision, not silently accepted.
7. **Write the narrative.** `data/entity-model.md` covers what SQL cannot express:
   source of truth, ownership boundaries, sensitivity classification, retention
   and deletion, audit needs, import/export paths, and migration risk.
8. **Check drift** against what actually shipped:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/schema-drift-check.py"
   ```

9. **Convene the council** via `run-engineering-council` before any irreversible
   or high-blast-radius migration.
10. **Validate:**

    ```bash
    python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" <artifact paths>
    ```

## Arguments

| Flag | Effect |
| --- | --- |
| `--initiative <id>` | Target a specific initiative instead of the active one. |
| `--introspect` | Start from the live database rather than a blank schema. |
| `--regenerate` | Re-derive `data-model.json` and `erd.mmd` from `schema.sql` and stop. |

## Outputs

| Path | Owner | Role |
| --- | --- | --- |
| `data/schema.sql` | **human** | Source of truth. Full DDL. |
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

- Never hand-edit `data-model.json` or `erd.mmd`. Edit `schema.sql` and regenerate.
- Do not propose destructive migrations without explicit risk and rollback notes.
- Enable RLS on every table exposed to a client, and write the policies. RLS
  enabled with no policy denies everything, which is safe but not finished.
- Mark sensitive fields and retention assumptions. The generated `sensitive_hint`
  flags are prompts for a human decision, not a classification.
- Never put real credentials or connection strings in any artifact.
- Record unresolved source-of-truth questions under Open Questions; they are
  scraped into the open-questions store automatically.

## Related Agents

- `domain-modeller`
- `database-engineer`
- `security-reviewer`
