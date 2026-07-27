# Workspace Contract

Engineering Lifecycle writes into two trees under `.project/`, split by audience.

**`.project/.engineering/`** is machine state: the ledger, reports, detected
context, council runs, hygiene, dashboards, the open-questions store and the
initiative registry. It is regenerable, and gitignored by default.

**`.project/docs/engineering/<initiative-id>/`** holds the narrative deliverables
a person reads: the PRD, technical design document, app flow, design system, and
engineering plan. These are the documents the work produces, so they are kept out
of a dot-directory full of runtime state.

```text
.project/docs/engineering/<initiative-id>/
  prd.md
  technical-design-document.md
  app-flow.md
  screen-inventory.md
  engineering-plan.md
  task-breakdown.md
  discovery-brief.md
  design-system/
  data/                         # schema.sql, data-model.json, erd.mmd, entity-model.md
  system-map/
  api/
```

Run `scripts/migrate-artifact-paths.py` to move an existing workspace across. It
is dry-run by default and preserves git history where git is available.

## Directory Structure

```text
.project/.engineering/
  profile/
  lifecycle/
  context/                      # stack.json and other detected facts
  initiatives/<initiative-id>/
    discovery/
    requirements/
    ux/
    system-map/
    architecture/
    data/
    api/
    design-system/
    prototype/
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
  questions/                    # open-questions.json + a readable digest
  dashboards/
  reports/
```

`design-system/` and `prototype/` were written by skills for some time before
being recorded here. `maintenance/` and `handoffs/` are declared but currently
have no producer.

## Rules

- Machine state goes under `.project/.engineering`; narrative deliverables go
  under `.project/docs/engineering/<initiative-id>/`.
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
- Questions the assistant needs a human to answer belong under `questions/`.
  Write them there rather than leaving them only as `## Open Questions` prose:
  an artifact heading is scraped into the store automatically, but a question
  raised mid-conversation is lost unless it is recorded.

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
skill: create-technical-design-document
status: draft
created_at: 2026-06-27T00:00:00+10:00
---
```
