# Changelog

## Unreleased

### Added

- **Initiatives have an identity.** An initiative previously existed only as a directory name the model invented while writing the first artifact into it: no registry, no active pointer, no create/switch/close verb, and `active_initiative_resolver` — the one function that could answer "which initiative are we in?" — was never called by anything. A session that pivoted to unrelated work therefore kept filing it under whichever folder it started in, and nothing noticed. There is now a registry (`initiatives/registry.json`), an `/initiative` command (`new`, `switch`, `close`, `list`), and a drift check on `UserPromptSubmit` that scores each prompt against the active initiative and tells the model to stop and ask when the topic does not overlap. The `PreToolUse` edit guard asks again if a write still targets a non-active initiative. Resolution now scores token overlap against the registry and each initiative's artifacts, so "the push notification work" matches `push-notifications`; the previous literal-substring test required the slug typed verbatim and gave up entirely with two or more initiatives.
- **A durable store for questions the assistant needs answered.** Open questions lived only as free-text `## Open Questions` headings inside individual artifacts: never aggregated, never statused, never surfaced again after the turn that wrote them. Council questions had no destination at all, and the `AskUserQuestion` hook returned `allow` while recording nothing. `questions/open-questions.json` now collects them from four producers — the AskUserQuestion hook, artifact headings, council runs, and skills — beside a human-readable digest. Entries carry a stable id so re-scanning an artifact updates rather than duplicates, and an answered question stays answered across rescans. Unanswered questions are surfaced on every turn and on the dashboard.
- **The data model is a schema file, not prose.** `create-data-model` emitted an entity table and a nine-line Mermaid sketch, so nothing downstream could read the model back and later backend work re-derived it from whatever code was nearby. `schema.sql` is now the source of truth; `data-model.json` and `erd.mmd` are generated from it. A `PreToolUse` hook injects the entity and relationship list into any edit touching backend, migration, schema or ORM files, and escalates to a confirmation prompt when an edit introduces a table the model does not contain. A `PostToolUse` check reports divergence between the model and shipped migrations. Ported `generate-migration.py` and `schema-introspect.sh` from the shelved `database-design` plugin.
- **Eight design-style presets and an anti-slop register for `build-ui-prototype`.** Five mode flags (`--image-to-component`, `--component-redesign`, `--web-page-design`, `--clickable-prototype`, `--scaffold-app`), a required design-system resolution step, and eight presets (brutalist, minimalist, glassmorphism, neumorphism, material-design, flat-design, editorial, futuristic) each shipping a `style.md` and a self-contained `starter.html` on one shared token contract. `references/anti-slop-register.md` records the patterns that make generated interfaces read as machine-made, each with the condition under which it is legitimate, and `anti-slop-check.py` detects the mechanical subset. Adapted in part from [taste-skill](https://github.com/Leonxlnx/taste-skill) (MIT).
- **Stack-agnostic design systems.** `create-design-system` was React/Next/Tailwind-shaped throughout. Seven adapters now cover React with and without Tailwind, Vue/Nuxt, native PHP, WordPress, Laravel Blade and static HTML, selected from `context/stack.json` or forced with `--adapter`. Every adapter emits CSS custom properties as the common layer, so a component ports by changing its wrapper rather than its values.
- **Playwright, in two places.** `create-test-strategy` can drive a real browser from the terminal via `playwright_cli.sh` / `.ps1` before writing a strategy about behaviour it has not observed, and authors E2E specs rather than only describing them. Separately, `project-dashboard.html` — the only browser-facing artifact the plugin produces — now has five specs covering rendering, search, chip filtering, column sorting, and that it makes no external requests.
- `bin/eng-dev` reports where the running plugin copy came from and how far behind the checkout it is, and clears regenerable litter from an install directory.
- `/initiative` and `scripts/migrate-artifact-paths.py`, the latter moving a pre-split workspace into the two-tree layout.

### Changed

- **Generated output is split by audience.** `.project/.engineering/` keeps machine state (ledger, reports, context, council, hygiene, dashboards, questions, registry); `.project/docs/engineering/<initiative-id>/` holds the documents people read — PRD, technical design document, app flow, design system, engineering plan, data model. Both trees are scanned by the ledger and the artifact validator.
- **`create-architecture-plan` is now `create-technical-design-document`**, with detailed design per component, data and API design, cross-cutting concerns, and a required Environments section covering preview, development and production. Docker is treated as a decision to justify, not a default.
- **`create-implementation-plan` is now `create-engineering-plan`**, and writes `.project/.engineering/current-plan.json`. The `edit-scope-guard` hook reads that file and had nothing to check against, so it had never once fired.
- `create-prd` gained non-goals, user stories, assumptions, dependencies, success metrics and release criteria, all enforced. The duplicate root PRD template was removed.
- `quality_tools.py` passed 2,400 lines, so stack detection, the questions store and initiative identity were extracted into `stack_detection.py`, `questions.py` and `initiatives.py`. All three are re-exported from `quality_tools` so existing callers are unaffected. `initiative_drift_detector` now takes the classified intent as an argument, which is what keeps `initiatives` from importing `quality_tools` back.
- `run_tool` dispatches through a lookup table instead of 57 sequential `if name ==` comparisons, with the resolved context passed as a single `ToolContext` rather than recomputed per branch. The point is not the lookup cost: a table can be enumerated, so a test now walks every registered tool against every dispatcher script and hook wrapper on disk. It failed on its first run and found five tool names nothing could reach — `block-dangerous-bash` and `block-secret-exfil` (the shell wrappers exec the guards under their real names) and `detect-new-env-vars`, `suggest-gitignore-updates` and `validate-generated-artifacts` (self-contained hook scripts that never enter `cli_main`). All five were equally dead inside the if-chain, where nothing could have found them.
- CI runs on Windows as well as Linux. The codebase is developed on Windows and its guards match Windows commands, so a Linux-only matrix could not see a whole class of breakage.

### Removed

- `build-project-dashboard`. `sync-ledger.py` already aggregated the workspace and rendered the dashboard on every edit, so the skill only re-ran what a hook had already done. A `Stop`-hook sync was added to catch artifacts written by `Bash`, which never fires `PostToolUse`.
- `sync-linear-tasks`. `eng-life linear-sync` and `linear-sync.py` remain.

### Fixed

- **Stack detection returned empty arrays for every monorepo.** `detect_stack` stat'd a fixed set of markers at the repo root and read only the root `package.json`, looking for the literal keys `react` and `vue`. It knew four frameworks, two backends and one database. A pnpm or turbo repo keeps its real dependencies in workspace members and its Supabase or Cloudflare config in sibling folders, so `frameworks`, `backend` and `database` all came back empty — while `pnpm-workspace.yaml` was read as an existence marker whose `packages:` globs were never expanded. Detection now resolves workspace members, reads their manifests, recognises a far wider vocabulary across JS, Python, PHP, Go, Rust, Ruby, Java and .NET, and records the file or dependency that proved each finding. `test_commands` is verified against the scripts that actually exist rather than templated from the package manager, which is why this repo had been advertising `pytest` while running `unittest`.
- **`load-project-memory` returned a file listing and nothing called it.** It `rglob`'d three directories for paths without opening a single file, omitted `initiatives/` entirely, and injected a bare timestamp into a dict of lists so any consumer iterating the values walked it character by character. It now reads decision summaries, profile values, ledger counts and initiative structure, and runs at `SessionStart`.
- Empty `interface.privacyPolicyURL` and `interface.termsOfServiceURL` in the Codex manifest, which the validator rejects when provided but blank. The keys are omitted rather than pointed at pages that do not exist. Both sibling plugins had the same defect. Two validators now enforce it.
- `__pycache__` no longer accumulates inside an installed plugin directory: every hook and CLI entrypoint runs Python with `-B`. The related symptom — edits to a source checkout appearing to do nothing — is a version-pinned install, not caching, and `bin/eng-dev status` now reports it.
- `dashboard-data.json` always emitted `open_human_tasks` while the schema and template omitted it, so drift in the real artifact was never caught.
- The `secret-exfiltration-guard` was registered twice on `Bash`.
- `README.md` carried its own copy of the workspace tree, which drifted from `references/workspace-contract.md` the first time the contract changed. The README now points at the contract instead of duplicating it.

## 0.6.1 - 2026-07-22

### Fixed
- **Starting a session in a directory that is not a git repository no longer hangs.** `git_files()` falls back to a manual listing when `git ls-files` fails, and that fallback used an unpruned `rglob("*")`: the ignored set filtered the results but never stopped the traversal, so it still descended into `node_modules`, `__pycache__` and every vendored `.git`. Since `repo_root()` returns the working directory when it finds no repo above it, a session started in `~/.claude` walked the plugin cache and one clone per installed marketplace — pegging a CPU core and growing memory until the process was killed by hand. The fallback is now bounded three independent ways: roots that are never a project tree (a home directory, a filesystem root, an agent config tree) are refused outright, dependency and build directories are pruned during traversal instead of filtered after it, and both depth and file count are capped. `profile-repo`, `repo-context-pack` and changed-file classification share that fallback and are fixed with it.
- `detect-stack` no longer lists the repository at all. Every marker it tests is meaningful only at the repo root, so it stats that fixed set directly, and the one check that genuinely needed recursion — `prisma/schema.prisma` — uses a depth-bounded search that still finds the monorepo layout. It now also detects markers that exist but are untracked, which the `git ls-files` lookup missed on a fresh checkout. Measured on `~/.claude`: `git_files()` 19ms and the SessionStart hook 276ms, against no termination at all before.
- The catalog record and the Claude marketplace entry still advertised 0.5.0. The 0.6.0 release bumped only the two plugin manifests and the changelog, leaving `marketplace/plugins/engineering-lifecycle.json` and `.claude-plugin/marketplace.json` two releases behind and `johns-os-marketplace.py validate` failing on version drift. Releases now go through `bump-version`, which moves all four surfaces in lockstep.
 - `test_cli_uses_target_root_for_workspace_outputs` failed on every run. To prove a `--root` run had not polluted the plugin's own workspace it read `ROOT/.project/.engineering/workspace.json` unconditionally — an assumption 0.6.0 invalidated by making the workspace opt-in and never auto-created. The test now samples whether that workspace exists before the run and asserts on both outcomes, and never creates it.

## Unreleased

### Added

- Public website metadata and cross-surface marketplace consistency validation.
- Root repository linting, pre-commit, CI, and public-release documentation.

### Fixed

- Removed the unsupported `$schema` field from `hooks/hooks.json` so the plugin hook loader accepts the configuration.

## 0.6.0 - 2026-07-18

### Changed
- **The `.project/.engineering` workspace is now opt-in per repo and never auto-created.** Previously every session start ran `init-workspace.py`, and several `PostToolUse`/`Stop` hooks created the workspace as a side effect of writing reports — so `.project` appeared unbidden in any repo (and, because those hooks anchored to `Path.cwd()`, in random subfolders too). The workspace is now created only by an explicit action: the new `/project-init` command, `eng-life init`, or a lifecycle skill writing its first artifact. Until then the plugin stays dormant.
- SessionStart no longer initializes the workspace. When none exists, the new `session-start-context.py` hook asks — via `AskUserQuestion` — whether to run `/project-init`, and never creates `.project` itself. `detect-stack` still runs but only persists `stack.json` once the workspace exists.
- All workspace-writing hooks now anchor to the **repo root** (via `engineering_root`/`repo_root`) instead of `Path.cwd()`, so a hook firing while the working directory is a subfolder can no longer drop a stray `.project` there. Affected: `capture-session-summary`, `detect-new-env-vars`, `suggest-gitignore-updates`, `validate-generated-artifacts`.

### Added
- **`/project-init` command** — the explicit, idempotent way to create the workspace. Defaults to the repo root; `/project-init here` targets the current subfolder (via a new `--here` flag on `init-workspace.py`) for deliberate nested-package layouts.
- `eng_common.workspace_exists()` — single source of truth for whether a repo has opted in; every automatic hook gates on it.
- Regression test asserting no hook wired into `hooks.json` creates `.project` (at the repo root or in a subfolder) when the workspace is absent.

### Removed
- `hooks/scripts/session-start-context.sh` (replaced by the repo-root-aware, opt-in-respecting `session-start-context.py`).

## 0.5.0 - 2026-07-16

### Changed
- **Artifact validation is stricter — existing artifacts may now fail.** `validate-artifact.py` now enforces the section contracts the skills already documented: `prd` requires all 10 sections (adds `Users`, `Permissions And Data Handling`, `Edge Cases`) and `release-plan` requires all 8 (adds `Post-Release Validation`, `Open Questions`). Only 7 and 6 were enforced before, so PRDs and release plans that previously passed may fail until the missing sections are added.
- Skills now declare scoped `allowed-tools`. 17 of 20 skills carry a minimal allowlist. `sync-linear-tasks`, `build-ui-prototype` and `implement-feature-safely` are intentionally left unrestricted: the first drives Linear MCP tools whose server name is install-specific and cannot be allowlisted, and the other two run open-ended project validation commands that cannot be enumerated.
- `sync-linear-tasks` push safety is now a hard gate rather than advice: every push confirms first, batches creating or updating more than 5 issues require explicit approval of the full plan, and descriptions must be redacted before upload.

### Fixed
- Skill workflows invoked plugin scripts by a plugin-root-relative path (`python scripts/validate-artifact.py`), which only resolved when the working directory happened to be the plugin root — so documented validation steps could silently skip. All 22 invocations across 17 skills are now anchored to `${CLAUDE_PLUGIN_ROOT}`, matching `hooks.json`.
- The `create-ux-flow` eval asserted output containing "Happy Path", which no template or example emits (the canonical section is `Journeys`) and which contradicted the eval's own judge criteria.
- `review-change` did not document the `empty-argument` and `no-diff` edge behaviour that its evals assert; both are now specified.
- Removed a dangling `task-tracker` agent reference from `sync-linear-tasks`.

### Removed
- The generated runtime workspace under `.project/` is no longer tracked. It is session-hook output rather than source, nothing referenced it, and it is now gitignored.

## 0.4.0 - 2026-07-10

Supersedes 0.3.0, which was tagged the same day carrying this identical content and re-versioned minutes later as part of a marketplace-wide release. 0.3.0 shipped nothing separately, so it has no entry of its own.

### Added
- Linear task tracking: the `sync-linear-tasks` skill plus a deterministic `linear-sync.py` engine (idempotent push, status-only pull), an intake reminder when tasks are unsynced, and an `eng-life linear-sync` subcommand.
- Human-task ingestion: the ledger and dashboard now aggregate `human-tasks.json` alongside action items.
- Proactive engineering council: the user-prompt intake now suggests the council before high-stakes work (word-boundary + scale-score triggers), the `run-engineering-council` skill orchestrates its six subagents for real multi-perspective analysis, and a configurable `council-config.json` enforcement level (off/remind/ask) tunes the suggestion.
- `env_var_inventory` in the hygiene report: every referenced variable with an accurate `in_env_example` flag.

### Fixed
- Environment-example detection ignored app/package-level templates; discovery is now centralized in `eng_common` (ancestor-walk) and applied to both detectors and the apply side.

## 0.2.0 - 2026-06-30

### Added
- Production-oriented lifecycle examples, stronger templates, and repository `.gitignore` hygiene.

### Changed
- Rewrote specialist and council agent prompts with evidence rules, boundaries, and structured output contracts.

### Fixed
- Hardened hook command resolution, CLI target-root handling, schema validation, prompt trigger evals, and live council adapter support.

## 0.1.0 - 2026-06-27

### Added
- Initial release: runtime scaffolding for lifecycle phases 2-6.
- Conservative hygiene detection, ledger sync, dashboard generation, and deterministic council artifacts.
