# Changelog

All notable repository-level changes are documented in this file.

This changelog covers the `johns-os` marketplace, shared repository tooling, public documentation, and changes affecting multiple plugins. Detailed changes to an individual plugin remain in that plugin's own `CHANGELOG.md`.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow Semantic Versioning where a repository marketplace version was recorded.

## [Unreleased]

### Added

- Added `cli/`, an `npx johns-os` installer for the marketplace with `install`, `list`, `update`, `init` and `doctor`. It is dependency-free because it runs via `npx` on machines that have nothing set up. `doctor` reports where an installed plugin is actually executing from and how far behind the local checkout it is — a gap that is otherwise invisible, since plugins run from a version-pinned copy under `~/.claude/plugins/cache/` and a git-sourced marketplace fetches from the remote rather than from disk.
- Added `scripts/check-cli-version.py`, run by `validate-repo.py`, so the installer can never advertise a marketplace version that does not exist.
- Added `.github/workflows/e2e.yml`, an opt-in Playwright job covering the generated project dashboard. It is separate from CI because it is the only thing in the repository needing Node and a browser download.
- Added `.github/workflows/publish-cli.yml`, manual-dispatch only, with a dry-run default.

### Changed

- CI now runs on Windows as well as Linux. The codebase is developed on Windows and contains Windows-specific guard patterns, so a Linux-only matrix could not see a whole class of breakage. Lint and formatting still run once, on Linux.
- `validate-repo.py` excludes generated Node and fixture directories from `compileall`.

### Fixed

- Removed empty `interface.privacyPolicyURL` and `interface.termsOfServiceURL` from all three plugins' Codex manifests. Codex rejects those keys when provided but blank, so an empty string is strictly worse than omitting the key. `johns-os-marketplace.py validate` now enforces this across every plugin in the catalogue rather than leaving it to each plugin's own validator.

## [0.3.0] - 2026-07-16

### Added

- Added the `ai-utilities` plugin, consolidating Claude Code extension authoring, skill review, plan-completion auditing, and audit-resolution workflows.
- Added root Ruff, yamllint, pre-commit, development dependency, and GitHub Actions CI configuration.
- Added `scripts/validate-repo.py` as the single deterministic repository validation entry point.
- Added cross-surface marketplace consistency tests covering Claude Code, Codex, and the local catalogue.
- Added public contribution, security, code-of-conduct, support, issue-template, pull-request-template, funding, and Dependabot configuration.
- Added a safe root `.env.example` for optional engineering-council adapters and test fixtures.
- Added repository-wide editor, line-ending, ignore, and credential-safety defaults.

### Changed

- Repositioned `johns-os` as a public-ready Claude Code and Codex plugin marketplace for software delivery, business development, and AI-assisted repository work.
- Expanded the active marketplace to three plugins: `engineering-lifecycle`, `business-development`, and `ai-utilities`.
- Added Web Lifter homepage metadata to active Claude Code marketplace entries.
- Documented the repository architecture, installation paths, development setup, validation commands, and the boundary between active plugins and `_unreleased/` candidates.
- Standardised Python formatting and linting across the repository.
- Excluded generated `.project/` state and `_unreleased/` working material from the public source boundary and automated checks.

### Fixed

- Resolved existing Ruff findings and formatting drift before public release.
- Corrected historical plugin changelog entries using commit and release history rather than leaving shipped work under `Unreleased`.

## [0.2.0] - 2026-07-10

### Added

- Added the `business-development` plugin with an interview-first `service-outline` workflow.
- Added a service-document analysis agent and quick-mode support to the business-development workflow.
- Added deterministic Linear task synchronisation, human-task ingestion, proactive council orchestration, configurable enforcement, and environment-variable inventory capabilities to `engineering-lifecycle`.
- Added marketplace tooling to update every version surface atomically through the `bump-version` command.

### Changed

- Expanded `johns-os` from a single-plugin marketplace into a multi-plugin catalogue.
- Released marketplace version `0.2.0`, `engineering-lifecycle` version `0.4.0`, and `business-development` version `0.2.0` together.
- Updated Claude Code, Codex, and local catalogue metadata to represent the expanded plugin set.

### Fixed

- Resolved marketplace version drift between plugin manifests, catalogue records, and the Claude Code marketplace entry.
- Fixed environment-example discovery in nested applications and packages.
- Fixed engineering-council triggering and human-task aggregation reliability.

## [0.1.0] - 2026-06-29

### Added

- Established `johns-os` as a plugin marketplace with Claude Code, Codex, and local catalogue metadata.
- Added the official root `.claude-plugin/marketplace.json` manifest so the repository could be installed through Claude Code's marketplace flow.
- Registered the initial `engineering-lifecycle` plugin for structured discovery, requirements, UX, architecture, implementation, testing, release, and repository-hygiene work.
- Added deterministic marketplace discovery and validation commands.
- Added the initial repository README with installation instructions and marketplace architecture.

### Changed

- Promoted the repository from a local catalogue structure to an installable Claude Code marketplace while retaining parallel Codex metadata.

[Unreleased]: https://github.com/johnoconnor0/johns-os/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/johnoconnor0/johns-os/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/johnoconnor0/johns-os/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/johnoconnor0/johns-os/releases/tag/v0.1.0
