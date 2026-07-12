# Changelog

## 0.1.0 - 2026-07-12

### Added
- Initial release of the consolidated `ai-utilities` plugin for the johns-os marketplace,
  merging two former plugins into a single namespace:
  - `skill-creator` and `skill-review` (from the former `skill-ops` plugin, v2.1.1).
  - `plan-completion-audit` and `audit-resolver` plus the `audit-resolve` command (from the
    former `plan-review` plugin, v2.2.2).
- Merged hook wiring: a SessionStart welcome, a PreToolUse skill-content guard, and PostToolUse
  skill/script quality checks.

### Changed
- Namespaced all command references to `ai-utilities` (e.g. `/ai-utilities:audit-resolve`,
  `/ai-utilities:plan-completion-audit`).
- Repointed `skill-review` delegation from the non-existent `skill-evaluator` to the bundled
  `skill-review` skill.
- Repository/homepage metadata repointed to the johns-os marketplace.
