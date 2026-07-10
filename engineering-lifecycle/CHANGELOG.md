# Changelog

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
