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

## Workflow

1. Confirm implementation is requested and identify the accepted plan or inline plan for small changes.
2. Inspect affected source, tests, configs, package scripts, docs, generated artifacts, and hygiene reports before editing.
3. State the scoped slice being implemented, expected files, tests to run, rollback path, and docs/hygiene checks.
4. Make small changes that match the accepted scope; pause and ask before editing files outside scope or touching sensitive/generated files.
5. Run the smallest relevant validation commands available and record exact results.
6. Update implementation log, action items, and hygiene artifacts when relevant.

## Outputs

- Source changes when explicitly requested.
- `.project/.engineering/initiatives/<initiative-id>/implementation/implementation-log.md`
- Updated hygiene artifacts when relevant.

## Required Sections

- Plan Followed
- Changes Made
- Tests Run
- Hygiene Updates
- Residual Risk
- Follow-Ups

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
