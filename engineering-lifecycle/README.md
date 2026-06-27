# Engineering Lifecycle

Engineering Lifecycle is a Claude Code plugin for moving software products through a structured engineering lifecycle. It helps teams profile a product system, define requirements, map UX and architecture, design data and API contracts, plan implementation, review changes, test, release, and maintain repository hygiene.

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

The repository URL is not declared in the manifest yet because the final public URL is not known in this scaffold. Add it only when the new repository URL is confirmed.

## Quick Start Workflow

1. Profile the product system with `profile-product-system`.
2. Map lifecycle state with `map-product-lifecycle`.
3. Create missing artifacts with the relevant lifecycle skill.
4. Plan implementation with `create-implementation-plan`.
5. Implement only after the plan is accepted, using `implement-feature-safely` when execution support is needed.
6. Review, test, and release with `review-change`, `create-test-strategy`, and `create-release-plan`.
7. Maintain repo hygiene with `update-repo-hygiene` and the conservative hook checks.

## Workspace Contract

Generated artifacts use this project-local namespace:

```text
.project/.engineering/
  profile/
  lifecycle/
  initiatives/<initiative-id>/
    discovery/
    requirements/
    ux/
    system-map/
    architecture/
    data/
    api/
    implementation/
    review/
    testing/
    release/
    maintenance/
  decisions/
  handoffs/
  hygiene/
  ledger/
  council/
  dashboards/
  reports/
```

Rules:

- Generated artifacts go under `.project/.engineering`.
- Artifact files should use readable Markdown, YAML, or JSON.
- Draft and approval state must be explicit in front matter or sidecar metadata.
- Do not store secrets or copied credential values.
- `.env.example` may contain variable names and placeholder values only.

See `references/workspace-contract.md` for the full contract.

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
- `create-system-map`: map actors, components, workflows, data flow, boundaries, risks, and deployment shape.
- `create-architecture-plan`: turn system understanding into architecture decisions and ADR candidates.
- `create-data-model`: define entities, relationships, ownership, sensitivity, retention, and migration risk.
- `create-api-contract`: define service, frontend, backend, webhook, event, or external-system interfaces.
- `create-implementation-plan`: sequence work into safe implementation slices with tests and rollback notes.
- `implement-feature-safely`: guide implementation after planning, with verification and hygiene checks.
- `review-change`: review a branch, diff, PR, or local change for correctness, risk, and maintainability.
- `create-test-strategy`: define unit, integration, contract, E2E, regression, load, security, and manual QA coverage.
- `create-release-plan`: define release, migration, rollout, monitoring, rollback, and support steps.
- `run-engineering-council`: run optional council review for high-stakes engineering decisions.
- `update-repo-hygiene`: inspect and intentionally update supporting repo hygiene files.
- `build-project-dashboard`: summarize lifecycle state, action items, risks, and recent artifacts.

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

## Hooks

Hook behavior is conservative, deterministic, and rooted through `CLAUDE_PLUGIN_ROOT` so installed plugin hooks can run from a target project.

- `SessionStart`: fast repo and context detection only.
- `PreToolUse`: dangerous command, production command, generated-file, sensitive-file, edit-scope, and secret-exfiltration guards.
- `PostToolUse`: hygiene drift detection after edits.
- `Stop`: completion and hygiene reminders.

Canonical hook scripts:

- `session-start-context.sh`
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

## Runtime Boundaries

- No bundled live MCP integrations.
- No custom LSP behavior beyond static plugin metadata.
- Hook scripts detect, report, validate, and sync generated lifecycle state.
- Controlled support-file edits are limited to `.env.example`, `.gitignore`, `.dockerignore`, `README.md`, `CHANGELOG.md`, and `CLAUDE.md`.
- The council is optional, deterministic by default, supports explicit live adapters, and should be manually invoked for high-stakes tradeoffs.
- Dashboard output is `.project/.engineering/dashboards/project-dashboard.html` plus `dashboard-data.json`.
