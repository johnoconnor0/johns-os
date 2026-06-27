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

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/data/entity-model.md`
- `.project/.engineering/initiatives/<initiative-id>/data/erd.mmd`

## Safety Constraints

- Do not propose destructive migrations without explicit risk notes.
- Mark sensitive fields and retention assumptions.
- Identify unknown source-of-truth questions.

## Related Agents

- `domain-modeller`
- `database-engineer`
- `security-reviewer`
