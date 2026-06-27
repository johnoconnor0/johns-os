---
name: implement-feature-safely
description: Use only after planning to guide implementation in small verified slices while respecting architecture, tests, repository conventions, and hygiene.
---

# Implement Feature Safely

## Trigger

Use when the user explicitly asks to implement an approved plan or safely make a code change.

## When To Use

- After an implementation plan exists or the change is small enough to plan inline.
- When tests, docs, and hygiene updates must remain aligned.
- When the user wants execution support, not only planning.

## Inputs Inspected

- Implementation plan and related lifecycle artifacts.
- Existing source, tests, docs, config, and package scripts.
- Hygiene reports and workspace state.

## Outputs

- Source changes when explicitly requested.
- `.project/.engineering/initiatives/<initiative-id>/implementation/implementation-log.md`
- Updated hygiene artifacts when relevant.

## Safety Constraints

- Inspect before editing.
- Keep changes scoped to the accepted plan.
- Run relevant checks when available.
- Never copy secrets into artifacts or examples.

## Related Agents

- `frontend-engineer`
- `backend-engineer`
- `database-engineer`
- `repo-hygiene-maintainer`
- `qa-test-strategist`
