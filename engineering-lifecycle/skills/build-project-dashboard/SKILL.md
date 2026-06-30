---
name: build-project-dashboard
description: Use to summarize lifecycle state, artifacts, risks, action items, decisions, hygiene status, and release readiness into a project dashboard.
---

# Build Project Dashboard

## Trigger

Use when the user asks for a project status view, lifecycle dashboard, initiative summary, or current engineering state.

## When To Use

- After lifecycle artifacts exist.
- During maintenance or handoff.
- Before planning the next set of work.

## Inputs Inspected

- `.project/.engineering/lifecycle/`
- Initiative artifacts.
- Decisions, handoffs, hygiene reports, action items, and release notes.

## Workflow

1. Run `python scripts/sync-ledger.py` to refresh normalized project state.
2. Inspect `.project/.engineering/ledger/ledger.json` and `.project/.engineering/dashboards/dashboard-data.json`.
3. Artifact status is derived automatically (content/role-aware): Markdown uses its front-matter `status`; generated JSON/JSONL are classified as `valid`/`invalid`/`error` (validation reports), `generated`, `log`, `current`, or `council`. Files older than the staleness threshold are flagged `freshness: stale`. Never relabel real state as complete.
4. The generated `project-dashboard.html` is a self-contained, themeable page (light/dark, responsive) that surfaces summary chips, risks, missing artifact groups with remediation tips, open action items, council runs, and a searchable/sortable/filterable artifacts table. Confirm these are visible.
5. Re-run `python scripts/validate-schemas.py` after changing dashboard data fixtures or schema-backed JSON.

## Outputs

- `.project/.engineering/dashboards/project-dashboard.html`
- `.project/.engineering/dashboards/dashboard-data.json`

## Safety Constraints

- Status is derived from artifact content/role, not invented — do not hand-edit it to imply completion.
- Stale (`freshness`) and missing artifact groups must stay visible.
- Keep risks and follow-ups visible.

## Related Agents

- `repo-hygiene-maintainer`
- `qa-test-strategist`
- `devops-release-engineer`
