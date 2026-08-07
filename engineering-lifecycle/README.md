# Engineering Lifecycle

Engineering Lifecycle is a Claude Code plugin for moving software products through a structured engineering lifecycle. It helps teams profile a product system, define requirements, map UX and architecture, plan design systems, design data and API contracts, plan implementation, review changes, test, release, and maintain repository hygiene.

This plugin is the replacement for the previous `engineering-os` direction. It is a new plugin in a new repository shape. It does not depend on the old plugin, its workspace layout, or its compatibility behavior.

## Product Model

The plugin is lifecycle-first, not department-first.

Its operating model is:

- Lifecycle skills produce the main artifacts.
- Specialist agents provide focused judgment when a task needs domain review.
- Deterministic hooks detect safety and hygiene issues.
- Project artifacts are stored under `.project/.engineering`.
- The engineering council is optional and manual, reserved for high-stakes decisions.

## Installation Assumptions

This repository is shaped as a Claude Code plugin. Claude Code should discover plugin components by their default locations:

- `.claude-plugin/plugin.json`
- `skills/`
- `agents/`
- `hooks/`

The manifest intentionally avoids over-specifying component paths unless future validation shows that explicit paths are required.

The plugin website is declared in the manifests as https://weblifter.com.au.

### Running copy vs source checkout

An installed plugin executes from a version-pinned copy under
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, not from a working
tree. Edits to a source checkout do not reach a session until they are committed,
pushed, and the plugin updated. `bin/eng-dev status` reports the install path, the
pinned commit, and how far behind the checkout it is; `bin/eng-dev clean` removes
regenerable litter from the installed copy. Every hook and CLI entrypoint runs
Python with `-B` so bytecode is never written into an install directory.

The first line of every session reports the resolved plugin root and version, so
a stale install is visible immediately.

## Quick Start Workflow

1. Profile the product system with `profile-product-system`.
2. Map lifecycle state with `map-product-lifecycle`.
3. Create missing artifacts with the relevant lifecycle skill.
4. Create a design system with `create-design-system` when UI foundations, tokens, or reusable component standards are needed.
5. Plan implementation with `create-engineering-plan`.
6. Implement only after the plan is accepted, using `implement-feature-safely` when execution support is needed.
7. Review, test, and release with `review-change`, `create-test-strategy`, and `create-release-plan`.
8. Maintain repo hygiene with `update-repo-hygiene` and the conservative hook checks.

## Workspace Contract

Generated output is split across two trees under `.project/`, by audience:

| Tree | Holds | Audience |
| --- | --- | --- |
| `.project/.engineering/` | ledger, reports, detected context, council runs, hygiene, dashboards, open questions, initiative registry | machine state, regenerable, gitignored |
| `.project/docs/engineering/<initiative-id>/` | PRD, technical design document, app flow, design system, engineering plan, data model | the documents people read |

Rules:

- Machine state goes under `.project/.engineering`; narrative deliverables go under
  `.project/docs/engineering/<initiative-id>/`.
- Artifact files should use readable Markdown, YAML, or JSON.
- Draft and approval state must be explicit in front matter or sidecar metadata.
- Do not store secrets or copied credential values.
- `.env.example` may contain variable names and placeholder values only.

**`references/workspace-contract.md` is the single source of truth for the
directory layout.** It is deliberately not duplicated here: this file previously
carried its own copy of the tree, and the two drifted apart the first time the
contract changed. Read the contract for the full structure and stage list.

Run `scripts/migrate-artifact-paths.py` to move a workspace created before the
two-tree split; it is dry-run by default.

### Workspace initialization (opt-in)

The workspace is **opt-in per repo**. Nothing creates `.project` automatically —
not session start, not post-tool hooks, not stop hooks. It is created only by an
explicit action:

- **`/project-init`** — the recommended way. Creates `.project/.engineering` at the
  **repo root**. Run `/project-init here` from a subfolder to place it there instead
  (e.g. a nested package).
- **`eng-life init`** — the CLI equivalent.
- **Running a lifecycle skill** — a skill writing its first artifact creates the
  workspace on demand (also at the repo root).

Until then the plugin stays **dormant**: automatic hooks run but do not write, so
no `.project` directory appears. When a session starts in a repo without a
workspace, the SessionStart hook asks (via `AskUserQuestion`) whether to run
`/project-init` — it never creates the directory on its own. Every workspace write
is anchored to the repo root, so a hook firing while the working directory is a
subfolder can never drop a stray `.project` there.

## Lifecycle Stages

The canonical lifecycle is:

1. Discovery
2. Requirements
3. UX flow
4. System mapping
5. Architecture
6. Data model
7. API/interface contract
8. Implementation planning
9. Implementation
10. Review
11. Testing
12. Release
13. Monitoring/maintenance
14. Repo hygiene

See `references/lifecycle-model.md` for stage definitions, inputs, artifacts, exit criteria, and recommended next steps.

## Skills

The skills define production-oriented lifecycle contracts with repeatable workflows, evidence rules, templates, examples, and validation hooks.

- `profile-product-system`: inspect product, users, stack, repo shape, integrations, risks, and constraints.
- `map-product-lifecycle`: identify lifecycle state and missing artifacts.
- `create-discovery-brief`: turn a product idea or problem into a discovery brief.
- `create-prd`: produce practical requirements and acceptance criteria.
- `create-ux-flow`: map user journeys, screens, states, and interactions.
- `create-design-system`: plan or audit UI foundations, design tokens, component inventory, accessibility rules, and implementation mapping.
- `build-ui-prototype`: build a lightweight UI prototype, clickable MVP, app shell, dashboard mock, or frontend proof of concept.
- `create-system-map`: map actors, components, workflows, data flow, boundaries, risks, and deployment shape.
- `create-technical-design-document`: turn system understanding into architecture decisions and ADR candidates.
- `create-data-model`: design the database schema. Produces a durable `schema.sql`
  plus a generated JSON model and ERD that a `PreToolUse` hook reads back into
  every later backend edit.
- `create-api-contract`: define service, frontend, backend, webhook, event, or external-system interfaces.
- `create-engineering-plan`: sequence work into safe implementation slices with tests and rollback notes.
- `implement-feature-safely`: guide implementation after planning, with verification and hygiene checks.
- `review-change`: review a branch, diff, PR, or local change for correctness, risk, and maintainability.
- `create-test-strategy`: define unit, integration, contract, E2E, regression, load, security, and manual QA coverage.
- `create-release-plan`: define release, migration, rollout, monitoring, rollback, and support steps.
- `run-engineering-council`: run optional council review for high-stakes engineering decisions.
- `update-repo-hygiene`: inspect and intentionally update supporting repo hygiene files.

The project dashboard has no skill. `scripts/sync-ledger.py` aggregates the whole
workspace and rewrites `dashboards/project-dashboard.html` on every edit and again
at the end of a turn, so it is always current. `eng-life build-dashboard` forces a
rebuild if one is ever needed.

## Agents

Core agents:

- `product-discovery-lead`
- `requirements-analyst`
- `ux-flow-designer`
- `solution-architect`
- `domain-modeller`
- `api-contract-reviewer`
- `frontend-engineer`
- `backend-engineer`
- `database-engineer`
- `security-reviewer`
- `qa-test-strategist`
- `devops-release-engineer`
- `repo-hygiene-maintainer`

Council agents:

- `council-contrarian`
- `council-first-principles`
- `council-expansionist`
- `council-outsider`
- `council-executor`
- `council-chairperson`

Agents are specialists, not duplicates of skills. Delegate when isolated expert judgment, independent review, or focused analysis would improve the result.

## Commands

- `/project-init` — initialize the Engineering Lifecycle workspace for a repo (repo
  root by default; `/project-init here` for the current subfolder). This is the
  intended, explicit way to opt a repo into the workspace. See
  [Workspace initialization](#workspace-initialization-opt-in).
- `/initiative` — create, switch, close, or list initiatives (`new`, `switch`,
  `close`, `list`). See [Initiative identity](#initiative-identity).
- `/track` — file surfaced issues **into** the configured tracker, or configure
  tracking for the project.
- `/triage` — the other direction: pull what is already open **out of** the
  tracker, group it into workstreams, and fan out one read-only analysis agent per
  workstream. See [Triage](#triage).

## Triage

`/track` pushes; `/triage` pulls. They are separate commands because only one of
them needs `Agent`, and a filing command should not acquire the ability to spawn
subagents as a side effect.

The pipeline is three deterministic steps and one model-executed one:

1. `surface-issue.py fetch-plan` emits the search operations. Hooks and scripts
   cannot call MCP tools, so the model executes them — the same split that
   `build_plan`/`reconcile` already use for the push direction.
2. `surface-issue.py ingest` folds the results into the local queue, deduplicating
   against the `<!-- jos-issue: … -->` marker this plugin embeds in everything it
   files, then against the tracker's own id. Pulled items are recorded as `filed`,
   never `queued` — otherwise the next `/track file` would push them straight back
   as duplicates.
3. `triage.py compile` groups the queue with union-find over a weighted signal
   graph. Parent/child and blocking relations merge unconditionally; everything
   else needs **two signals to agree**, because no single weight reaches the merge
   threshold. `references/workstream-clustering.md` has the weights and the honest
   list of what it cannot see.
4. `triage.py dispatch-plan` renders one fully-formed agent prompt per workstream.

Every lifecycle agent is read-only (`Read, Glob, Grep`), so the fan-out is an
**analysis** pass — root cause, affected files, sequencing, risk, test gaps. That
parallelises freely and `parallel_safe` deliberately does not gate it: read-only
agents cannot collide. Implementation stays serial on the main thread through
`implement-feature-safely`, because `current-plan.json` is a single file and two
concurrent implementations would disable each other's edit-scope guard.

Only Linear ships a search shape. GitHub and Jira declare none on purpose — their
argument names were never verified against a live tool schema, and a plan built on
a guessed one fails at the MCP call with no useful message. `fetch-plan` says so
and names the overlay file that would supply one.

## Initiative identity

An initiative is one coherent piece of work, and every lifecycle artifact belongs
to exactly one. `initiatives/registry.json` records which exist and which is
**active**; new artifacts go there.

Three things keep that honest:

1. `UserPromptSubmit` scores each prompt against the active initiative. When the
   topic does not overlap, it tells the model to stop and ask whether this is new
   work rather than silently appending to the folder it started in.
2. The `PreToolUse` edit-scope guard asks for confirmation when a write targets a
   non-active initiative.
3. The registry adopts any folder created by hand, so it can never disagree with
   the filesystem.

Without these an initiative existed only as a directory name invented by whichever
skill wrote first, and a session that pivoted mid-way kept filing new work under
the old initiative.

## Hooks

Hook behavior is conservative, deterministic, and rooted through `CLAUDE_PLUGIN_ROOT` so installed plugin hooks can run from a target project.

- `SessionStart`: plugin provenance, fast repo and stack detection, and project
  memory recall. If no workspace exists it offers `/project-init` via
  `AskUserQuestion` — it never creates `.project`.
- `UserPromptSubmit`: intent, prompt quality, council trigger, unanswered open
  questions, and the initiative drift check.
- `PreToolUse`: dangerous command, production command, generated-file, sensitive-file, edit-scope, and secret-exfiltration guards.
- `PostToolUse`: hygiene drift detection and ledger/dashboard rebuild after edits.
- `Stop`: completion and hygiene reminders, plus a debounced ledger sync that
  catches artifacts written by `Bash` (which never fires `PostToolUse`).

Workspace-writing hooks (`SessionStart` stack detection, `PostToolUse` hygiene/ledger,
`Stop` capture/completion) are **dormant until the workspace exists** and always
anchor to the repo root, so they never auto-create `.project` or scatter it across
subfolders. Guard hooks (dangerous/secret/sensitive/scope) run regardless — they
only inspect and block, they never write.

Canonical hook scripts:

- `session-start-context.py`
- `block-dangerous-bash.sh`
- `block-secret-exfil.sh`
- `detect-new-env-vars.py`
- `suggest-gitignore-updates.py`
- `validate-generated-artifacts.py`
- `hygiene-stop-check.py`
- `sync-ledger.py`
- `capture-session-summary.py`

Hooks may detect and report. Broad automatic edits remain out of scope; controlled hygiene updates are available only through explicit commands.

## Engineering Council Live Adapters

The council is deterministic by default. Live model execution is opt-in and uses the same artifact boundary:

```bash
python scripts/council.py ask \
  --mode live-model \
  --adapter command \
  --question "Should we keep this as a modular monolith?" \
  --context .project/.engineering/initiatives/example/architecture/
```

Live adapter options:

- `command`: requires `ENGINEERING_COUNCIL_ADAPTER_COMMAND`; JSON is sent on stdin and Markdown or JSON content is read from stdout.
- `anthropic`: requires `ANTHROPIC_API_KEY` and `ENGINEERING_COUNCIL_MODEL`.
- `openai`: requires `OPENAI_API_KEY` and `ENGINEERING_COUNCIL_MODEL`.

Use `--fallback-on-error` when live model failure should fall back to deterministic local output.

## Script Layout

`scripts/` is two tiers. Most files are five-line dispatchers of the form
`from quality_tools import cli_main; raise SystemExit(cli_main("<name>"))`, which
exist so a hook or a skill can invoke one tool by path. The logic lives in a small
set of shared modules:

| Module | Owns |
| --- | --- |
| `eng_common.py` | Paths, the workspace contract, bounded filesystem scanning, IO, hook payload helpers |
| `quality_tools.py` | Prompt intake, guards, verification, hygiene, council, and the `run_tool` dispatch |
| `stack_detection.py` | Detecting frameworks, backends, databases and test tooling across a repo and its workspace members |
| `questions.py` | The open-questions store: recording, answering, scraping artifacts, rendering the digest |
| `initiatives.py` | The initiative registry, resolution, drift detection, and create/switch/close |
| `workstreams.py` | Clustering the issue queue into workstreams, and the parallel-safety verdict |
| `data_model.py` | Parsing `schema.sql` into a machine-readable model, the ERD, and drift against shipped migrations |

The last four were extracted from `quality_tools.py` once it passed 2,400 lines.
They are re-exported from `quality_tools` so every existing caller keeps working;
new code should import them directly.

`initiatives.initiative_drift_detector` takes the classified intent as an
argument rather than computing it. That is deliberate: prompt classification lives
in `quality_tools`, and calling it from `initiatives` would make the two modules
import each other.

### Adding a tool

`quality_tools.TOOLS` maps a tool name to a handler taking a single `ToolContext`
(the resolved root, hook payload, prompt, text, command, path and files). To add
one: write the function, add a line to `TOOLS`, and create a dispatcher shim in
`scripts/` so a hook or skill can invoke it by path.

Both halves are required. A test walks the table against every dispatcher and hook
wrapper on disk and fails if a shim names a tool that is not registered, or if a
registered tool has no way to be called.

## Runtime Boundaries

- No bundled live MCP integrations.
- No custom LSP behavior beyond static plugin metadata.
- Hook scripts detect, report, validate, and sync generated lifecycle state.
- Controlled support-file edits are limited to `.env.example`, `.gitignore`, `.dockerignore`, `README.md`, `CHANGELOG.md`, and `CLAUDE.md`.
- The council is optional, deterministic by default, supports explicit live adapters, and should be manually invoked for high-stakes tradeoffs.
- Dashboard output is `.project/.engineering/dashboards/project-dashboard.html` plus `dashboard-data.json`.
