---
name: create-data-model
description: Use to design entities, relationships, ownership, sensitive data handling, retention, audit needs, and migration risks.
---

# Create Data Model

## Trigger

Use when the user asks for entities, schema shape, ERD, storage boundaries, data lifecycle, migration planning, or data ownership.

## When To Use

- After architecture direction is clear.
- Before API/interface contracts.
- Before schema migrations or persistence-heavy features.

## Inputs Inspected

- Architecture plan and system map.
- Existing schema, migrations, models, ORM definitions, and storage config.
- Requirements and user workflows.

## Workflow

1. Inspect architecture, system map, requirements, workflows, current schemas, migrations, models, and storage configuration.
2. Define canonical entities, relationships, cardinality, lifecycle/status values, source of truth, and ownership boundaries.
3. Classify sensitive fields, retention/deletion behavior, audit needs, import/export paths, and permission implications.
4. Identify migration, backfill, rollback, and data integrity risks before proposing schema changes.
5. Render the entity model and ERD with unknowns marked explicitly.
6. For an irreversible or high-blast-radius migration, convene `run-engineering-council` before proposing the change.
7. Validate generated artifacts with `python scripts/validate-artifact.py <artifact paths>`.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/data/entity-model.md`
- `.project/.engineering/initiatives/<initiative-id>/data/erd.mmd`

## Required Sections

- Entities
- Relationships
- Ownership
- Sensitivity
- Retention
- Audit And Lifecycle
- Migration Risk
- Open Questions

## Safety Constraints

- Do not propose destructive migrations without explicit risk notes.
- Mark sensitive fields and retention assumptions.
- Identify unknown source-of-truth questions.

## Related Agents

- `domain-modeller`
- `database-engineer`
- `security-reviewer`
