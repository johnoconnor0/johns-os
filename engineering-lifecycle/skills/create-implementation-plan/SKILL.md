---
name: create-implementation-plan
description: Use to break approved product and architecture artifacts into sequenced, testable, low-risk implementation work.
---

# Create Implementation Plan

## Trigger

Use when the user asks how to build, sequence, scope, split, estimate, or safely implement a feature or change.

## When To Use

- After requirements and architecture are clear enough.
- Before source-code changes.
- When migration, rollout, or dependency ordering matters.

## Inputs Inspected

- PRD, UX flow, system map, architecture plan, data model, and API contract.
- Current codebase, test commands, package scripts, and repo conventions.

## Workflow

1. Inspect upstream artifacts, current code locations, test scripts, CI config, and migration/deployment constraints.
2. Split work into independently reviewable implementation slices.
3. For each slice, name likely files/modules, behavior to change, tests to add/run, rollback notes, and dependencies.
4. Separate required work from optional follow-ups.
5. Emit action items for unresolved questions, blocked dependencies, manual QA, and release prerequisites.
6. For a high-stakes, irreversible, or cross-cutting change, convene `run-engineering-council` before committing to the sequence.
7. Run `python scripts/validate-artifact.py .project/.engineering/initiatives/<initiative-id>/implementation/implementation-plan.md`.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/implementation/implementation-plan.md`
- `.project/.engineering/initiatives/<initiative-id>/implementation/task-breakdown.md`

## Required Front Matter

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

## Required Sections

- Goal
- Current State
- Implementation Slices
- Data Or Migration Work
- Test Plan
- Rollback
- Open Questions

## Safety Constraints

- Identify files or modules likely to change without editing them.
- Include tests, rollback, and migration notes when relevant.
- Separate required work from optional follow-ups.

## Related Agents

- `solution-architect`
- `frontend-engineer`
- `backend-engineer`
- `database-engineer`
- `qa-test-strategist`
