# Workspace Contract

Engineering Lifecycle stores generated project artifacts under `.project/.engineering` in the target project. This namespace is the active contract for the new plugin.

## Directory Structure

```text
.project/.engineering/
  profile/
  lifecycle/
  initiatives/<initiative-id>/
    discovery/
    requirements/
    ux/
    system-map/
    architecture/
    data/
    api/
    implementation/
    review/
    testing/
    release/
    maintenance/
  decisions/
  handoffs/
  hygiene/
  ledger/
  council/
  dashboards/
  reports/
```

## Rules

- Generated artifacts go under `.project/.engineering`.
- Use Markdown for narrative artifacts, YAML for structured human-editable profiles, and JSON for machine-oriented sidecars.
- Do not store secrets, copied credential values, tokens, private keys, or production connection strings.
- `.env.example` may contain variable names and placeholder values only.
- Every major artifact should declare draft/review/approval status in front matter or a sidecar file.
- Initiative work belongs under `initiatives/<initiative-id>/`.
- Cross-initiative decisions belong under `decisions/`.
- Agent handoffs belong under `handoffs/`.
- Hygiene reports belong under `hygiene/`.
- Action items and machine-readable state belong under `ledger/`.
- Council runs belong under `council/<run-id>/`.

## Artifact Status

Recommended statuses:

- `draft`
- `reviewed`
- `approved`
- `implemented`
- `superseded`

ADR statuses:

- `proposed`
- `accepted`
- `superseded`
- `rejected`

Action item statuses:

- `open`
- `in-progress`
- `blocked`
- `done`
- `deferred`
- `cancelled`

## Front Matter Pattern

```yaml
---
initiative_id: example-initiative
skill: create-architecture-plan
status: draft
created_at: 2026-06-27T00:00:00+10:00
---
```
