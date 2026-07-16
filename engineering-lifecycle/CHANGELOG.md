# Changelog

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

### Added
- Linear task tracking: the `sync-linear-tasks` skill plus a deterministic `linear-sync.py` engine (idempotent push, status-only pull), an intake reminder when tasks are unsynced, and an `eng-life linear-sync` subcommand.
- Human-task ingestion: the ledger and dashboard now aggregate `human-tasks.json` alongside action items.
- Proactive engineering council: the user-prompt intake now suggests the council before high-stakes work (word-boundary + scale-score triggers), the `run-engineering-council` skill orchestrates its six subagents for real multi-perspective analysis, and a configurable `council-config.json` enforcement level (off/remind/ask) tunes the suggestion.
- `env_var_inventory` in the hygiene report: every referenced variable with an accurate `in_env_example` flag.

### Fixed
- Environment-example detection ignored app/package-level templates; discovery is now centralized in `eng_common` (ancestor-walk) and applied to both detectors and the apply side.

## Unreleased

- Completed runtime scaffolding for lifecycle phases 2-6.
- Added conservative hygiene detection, ledger sync, dashboard generation, and deterministic council artifacts.
- Hardened hook command resolution, CLI target-root handling, schema validation, prompt trigger evals, and live council adapter support.
- Rewrote specialist and council agent prompts with evidence rules, boundaries, and structured output contracts.
- Added production-oriented lifecycle examples, stronger templates, and repository `.gitignore` hygiene.
