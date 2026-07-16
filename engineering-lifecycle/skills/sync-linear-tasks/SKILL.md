---
name: sync-linear-tasks
description: Push and reconcile the engineering-lifecycle ledger (AI action items + human tasks) to Linear, or pull issue status back. Use to set up Linear tracking, upload new/changed tasks as Linear issues, or reconcile status. Runs an idempotent deterministic plan so issues are never duplicated.
argument-hint: "[--setup] [--push] [--pull] [--dry-run]"
---

# Sync Linear Tasks

Keeps the local task ledger and Linear in step. Deterministic file work is done by
`scripts/linear-sync.py`; the actual Linear reads/writes happen here via the connected
Linear MCP (only the model can call MCP tools — hooks cannot).

## Trigger

Use when the user asks to sync, push, upload, or track tasks in Linear, to set up the Linear
integration, or to reconcile task status with Linear.

## When To Use

- First-time setup of the Linear integration for a project.
- After new action items or human tasks are added to the ledger.
- To reconcile status changes made by humans in Linear back into the ledger.

## Inputs Inspected

- `.project/.engineering/ledger/linear-config.json` (team, project, cycle, status_map, assignee_map, enforcement).
- `.project/.engineering/ledger/{action-items,human-tasks}.json` and `linear-state.json`.
- The connected Linear MCP tools (load via ToolSearch: `save_issue`, `list_issues`, `get_issue`, `list_teams`, `list_projects`, `list_issue_statuses`, `list_users`).

## Workflow

1. **Ensure config (or `--setup`).** Read `linear-config.json`. If missing or `team` is `"unknown"`, run setup: use `list_teams` / `list_projects` / `list_issue_statuses` to resolve the team, optional project/cycle, and build `status_map` (plugin status → the team's actual Linear workflow state names). Interview the user with `AskUserQuestion` to pick the team and project. Write `linear-config.json` from `templates/linear-config.template.json` and validate it against `schemas/linear-config.schema.json`.
2. **Build the plan.** Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/linear-sync.py" plan`. It returns only tasks that are new (`create`) or changed (`update`) since the last sync — nothing unchanged, so re-runs are no-ops.
3. **Push via MCP (`--push`, default).** For each plan entry call `save_issue`:
   - `create`: `title` + `team` (required), plus `description` (redact secrets/private data first — see Safety Constraints), `state` = `linear_state`, `priority`, `assignee` (from `assignee_map[owner]` or `"me"`), `project`, `cycle`, `labels` = `[label]`.
   - `update`: pass `id` = `linear_id` and the changed fields (especially `state`).
   Collect `{key, linear_id, linear_url}` for every issue. With `--dry-run`, print the plan and stop.
4. **Reconcile.** Write the collected results to a temp JSON file and run
   `python "${CLAUDE_PLUGIN_ROOT}/scripts/linear-sync.py" reconcile --results <file>` — it writes `linear_id`/`linear_url` back into the ledger and records the content hash so the next `plan` skips these.
5. **Pull (`--pull`).** `list_issues` filtered by team/label/project (and `updatedAt` since the last sync). For issues whose `linear_id` is known, map the Linear state back to a plugin status (reverse `status_map`), write `[{key, status}]` to a temp file, and run `python "${CLAUDE_PLUGIN_ROOT}/scripts/linear-sync.py" apply-pull --updates <file>`. Pull is **status-only** — it never overwrites local task content.
6. **Summarise.** Report created/updated/pulled counts and any tasks skipped for missing config.

## Outputs

- Updated `.project/.engineering/ledger/{action-items,human-tasks}.json` (with `linear_id`/`linear_url`).
- `.project/.engineering/ledger/linear-state.json` (sync state).
- Created/updated issues in Linear.

## Safety Constraints

- `save_issue` is mutating and creates live issues. **Always confirm via `AskUserQuestion` before pushing.** Run `--dry-run` first, and for any batch that creates or updates **more than 5 issues**, show the full plan and require explicit approval before calling `save_issue`.
- Push is **idempotent**: always go through `linear-sync.py plan` and pass `linear_id` on updates so issues are never duplicated. If a `linear_id` write-back fails, re-running is safe (the plan re-proposes the same update, not a new create).
- Pull reconciles **status only** — never overwrite local task titles/descriptions from Linear.
- **Redact before pushing.** Never place secrets or private data in issue descriptions, and never push unreviewed raw `source` text as a description — strip sensitive content first, or push the title only.
