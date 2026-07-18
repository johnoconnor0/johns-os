# Changelog

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
