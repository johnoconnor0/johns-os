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
  hygiene/                      # hygiene-report.json, rebuilt from parts/
    parts/                      # one file per producing hook; see below
  ledger/
  council/
  questions/                    # open-questions.json + a readable digest
  context/                      # stack.json, written every SessionStart
  tracker/                      # surfaced-issues.json + digest, dispatch state,
                                # workstreams.json + digest (see /triage)
  triage/analysis/              # one agent analysis per workstream
  dashboards/
  reports/
  settings.json                 # the one committed, hand-authored file here
```

## Root Resolution

Which workspace a command operates on is decided by one upward walk. Three
markers, nearest wins, and the workspace marker is tested first so a directory
carrying both answers "workspace".

| # | Rule | `reason` |
| --- | --- | --- |
| 1 | `--root` was given | `explicit` — used **verbatim**, no walk |
| 2 | walk starts at the passed directory, else `$CLAUDE_PROJECT_DIR`, else `cwd` | sets where the walk *begins*, never the answer |
| 3 | nearest addressable ancestor with `.project/.engineering` | `workspace` |
| 4 | nearest addressable ancestor with `.git` or `.claude-plugin/plugin.json` | `repo` |
| 5 | the starting directory | `fallback` |

The workspace marker exists because it is the only *deliberate* one. `.git` is
incidental — a nested package inside a monorepo has none of its own — so while
`.git` was the only marker, a workspace created by `/project-init here` could
never be addressed by anything that later read it. The create path and the
resolve path disagreed; that was the whole defect.

**The walk never descends.** That is what keeps a hook firing from a generated
subfolder from dropping a stray `.project` there: an ancestor walk can only land
on a directory somebody deliberately initialised, and it creates nothing.

**Not every directory may anchor a root.** Filesystem roots, `$HOME` and its
parents, the system temp directory, and anything with `.claude` or `.project` in
its path are refused. Machines that ran an early version of this plugin carry
debris workspaces in home and temp directories; without this guard, every
temporary directory would resolve to the temp root. `is_scannable_root` is the
same predicate, deliberately — a directory the plugin refuses to scan is one it
must also refuse to anchor to.

`eng-life doctor` prints the resolved root, the marker that proved it, every
ancestor carrying a workspace, workspaces nested below, and workspaces buried
inside `.project/` that cannot be addressed at all. Run it when a command
answers about the wrong project — that failure is silent otherwise.

`workspaces.json`, written only by `eng-life doctor --link`, is a convenience
index and is **never** an input to resolution. Resolution stays purely
filesystem-marker driven so it is correct when the index is missing, stale, or
from another machine.

`design-system/` and `prototype/` were written by skills for some time before
being recorded here.

**Declared with no producer**, as of this writing: `maintenance/`, `handoffs/`,
`council/` and `lifecycle/`. The first two were already recorded as such; the other
two were not, and an empty directory that nothing writes reads as a feature that
exists. `scripts/project-anomaly-check.py` compares this list against disk in both
directions, so a declaration that stops matching reality now surfaces rather than
waiting to be noticed.

**`settings.json` is the exception to everything else in this tree.** It is
hand-authored, belongs to the project rather than to a session, and is committed.
Because git cannot re-include a file whose parent directory is excluded, adopting it
needs the whole stanza rather than a single negation:

```gitignore
/.project/*
!/.project/.engineering/
/.project/.engineering/*
!/.project/.engineering/settings.json
```

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
- Hygiene reports belong under `hygiene/`. `hygiene-report.json` is a **derived
  view**: each detecting hook writes its own section to `hygiene/parts/<producer>.json`
  and the combined file is rebuilt from those. Several hooks fire concurrently on
  one edit, and while they shared the combined file each did a read-modify-write,
  so whichever finished second erased the other's section. Keys no producer owns
  — `risks`, `docs_updates`, whatever `update-repo-hygiene` wrote — are preserved
  across a rebuild. Write through `eng_common.write_hygiene_part`, never directly.
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
