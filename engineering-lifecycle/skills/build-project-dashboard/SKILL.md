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
3. Confirm missing or stale artifacts are marked as missing/unknown rather than inferred complete.
4. Open action items, risks, council runs, hygiene status, and recent artifacts must be visible.
5. Re-run `python scripts/validate-schemas.py` after changing dashboard data fixtures or schema-backed JSON.

## Outputs

- `.project/.engineering/dashboards/project-dashboard.html`
- `.project/.engineering/dashboards/dashboard-data.json`

## Safety Constraints

- Do not invent completion status.
- Mark stale or missing artifacts.
- Keep risks and follow-ups visible.

## Related Agents

- `repo-hygiene-maintainer`
- `qa-test-strategist`
- `devops-release-engineer`
