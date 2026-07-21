# Changelog

## 0.6.1 - 2026-07-22

### Fixed
- **Starting a session in a directory that is not a git repository no longer hangs.** `git_files()` falls back to a manual listing when `git ls-files` fails, and that fallback used an unpruned `rglob("*")`: the ignored set filtered the results but never stopped the traversal, so it still descended into `node_modules`, `__pycache__` and every vendored `.git`. Since `repo_root()` returns the working directory when it finds no repo above it, a session started in `~/.claude` walked the plugin cache and one clone per installed marketplace — pegging a CPU core and growing memory until the process was killed by hand. The fallback is now bounded three independent ways: roots that are never a project tree (a home directory, a filesystem root, an agent config tree) are refused outright, dependency and build directories are pruned during traversal instead of filtered after it, and both depth and file count are capped. `profile-repo`, `repo-context-pack` and changed-file classification share that fallback and are fixed with it.
- `detect-stack` no longer lists the repository at all. Every marker it tests is meaningful only at the repo root, so it stats that fixed set directly, and the one check that genuinely needed recursion — `prisma/schema.prisma` — uses a depth-bounded search that still finds the monorepo layout. It now also detects markers that exist but are untracked, which the `git ls-files` lookup missed on a fresh checkout. Measured on `~/.claude`: `git_files()` 19ms and the SessionStart hook 276ms, against no termination at all before.
- The catalog record and the Claude marketplace entry still advertised 0.5.0. The 0.6.0 release bumped only the two plugin manifests and the changelog, leaving `marketplace/plugins/engineering-lifecycle.json` and `.claude-plugin/marketplace.json` two releases behind and `johns-os-marketplace.py validate` failing on version drift. Releases now go through `bump-version`, which moves all four surfaces in lockstep.
- `test_cli_uses_target_root_for_workspace_outputs` failed on every run. To prove a `--root` run had not polluted the plugin's own workspace it read `ROOT/.project/.engineering/workspace.json` unconditionally — an assumption 0.6.0 invalidated by making the workspace opt-in and never auto-created. The test now samples whether that workspace exists before the run and asserts on both outcomes, and never creates it.

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
