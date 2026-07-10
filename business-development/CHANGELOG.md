# Changelog

All notable changes to the Business Development plugin are documented here.
The format is based on Keep a Changelog, and this project adheres to semantic versioning.

## [0.1.0] - 2026-07-10

### Added

- Initial `business-development` plugin (Claude Code + Codex manifests).
- `service-outline` skill: interview-first generation and updating of Service Outline
  documents from a modular 10-module template.
- Bundled 10-module template (`templates/modules/01..10-*.md`) reproduced from the Notion
  service template, with conditional Technical/Security/Compliance and AI Service addenda.
- Seven service-type profiles (`templates/service-types/*.yaml`) that switch the addenda and
  seed defaults: consulting, ai-engineering, software-development, web-design,
  ai-ppc-optimisation, branding, generic.
- Short-form Internal Service Brief template (`--brief`).
- Input adapters for `--update`: uploaded file, local path, Notion URL, web URL.
- `--refresh` to re-pull module templates from Notion (confirmation-gated).
- `scripts/validate-service-outline.py` deterministic validator.
- Service-type profile JSON schema, reference guides, a worked AI-PPC example, and an eval suite.
