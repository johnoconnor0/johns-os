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

1. Confirm an approved implementation plan exists, or — for a small change — an agreed inline plan. If neither exists, stop and run create-implementation-plan first.
2. Inspect affected source, tests, configs, package scripts, docs, generated artifacts, and hygiene reports before editing.
3. Implement one slice at a time: make the smallest change that satisfies the accepted scope, naming the expected files and rollback path; pause and ask before editing files outside scope or touching sensitive/generated files.
4. Run the smallest relevant validation commands available and record exact results. Never claim a check passed unless it was run.
5. Update the implementation log, action items, and hygiene artifacts when relevant.

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
