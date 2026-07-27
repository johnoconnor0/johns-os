---
name: create-engineering-plan
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*)
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
5. **Write the plan scope file.** Collect every file the plan expects to touch into
   `.project/.engineering/current-plan.json`:

   ```json
   { "initiative_id": "<id>", "created_at": "<iso>", "affected_files": ["src/..."] }
   ```

   The `edit-scope-guard` PreToolUse hook reads this file and asks for confirmation
   when an edit lands outside the plan. Without it the guard has nothing to check
   against and is inert, so an unplanned edit passes silently.
6. **Emit action items** for unresolved questions, blocked dependencies, manual QA
   and release prerequisites. Write them as `- [ ]` checklist lines in the plan,
   then ingest them:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/emit-action-items.py" <plan path>
   ```

   That writes `ledger/action-items.json`, which the dashboard and the Linear sync
   both read. A checklist that is never ingested is invisible outside the document.
   Put anything needing a **human decision** under `## Open Questions` instead; it
   is scraped into the open-questions store automatically.
7. For a high-stakes, irreversible, or cross-cutting change, convene `run-engineering-council` before committing to the sequence.
8. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" <artifact paths>`.

## Outputs

- `.project/docs/engineering/<initiative-id>/engineering-plan.md`
- `.project/docs/engineering/<initiative-id>/task-breakdown.md`
- `.project/.engineering/current-plan.json` (the scope the edit guard enforces)
- `.project/.engineering/ledger/action-items.json` (via `emit-action-items.py`)

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
