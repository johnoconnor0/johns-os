# Claude Code plugin design guide

## Purpose

A plugin is an installable extension bundle. Use it when a workflow needs multiple skills, agents, hooks, MCP/LSP configurations, monitors, commands, settings, or dependency declarations.

## Recommended structure

```text
<plugin-name>/
  .claude-plugin/
    plugin.json
  README.md
  CHANGELOG.md
  skills/
    <skill-name>/SKILL.md
  agents/
    <agent-name>.md
  hooks/
    hooks.json
    scripts/
  commands/           # optional; prefer skills for new workflows
  monitors/           # optional / experimental environments
  references/
  templates/
  examples/
  scripts/
  .mcp.json           # optional MCP server definitions
  .lsp.json           # optional LSP server definitions
  settings.json       # optional default settings
```

## Manifest planning fields

Use the current Claude documentation as source of truth, but a planning manifest normally records:

- plugin `name`, `description`, `version`, and author/publisher metadata;
- component paths for skills, agents, hooks, commands, MCP/LSP servers, monitors, or settings;
- optional user configuration;
- optional dependency declarations with semantic version ranges.

## Component principles

| Component | Use for | Avoid |
|---|---|---|
| Skills | Primary workflows and slash-invoked tasks | Packing many unrelated tasks into one skill |
| Agents | Specialist roles with isolated context | General instructions that belong in a skill |
| Hooks | Deterministic lifecycle guardrails | Reasoning-heavy audit judgement |
| MCP | External systems, resources, tools | Required access to every user's SaaS stack |
| LSP | Code intelligence | Hard failure when LSP is absent |
| Monitors/channels | Event streams into active sessions | Mandatory background processing |
| Commands | Legacy/simple slash wrappers | Duplicating skill logic |

## Semantic versioning

Use `MAJOR.MINOR.PATCH`.

- `MAJOR`: breaking schema, skill name, command, or manifest changes.
- `MINOR`: new skills, agents, optional integrations, references, or templates.
- `PATCH`: bug fixes, wording fixes, script fixes, examples, documentation.

Maintain a changelog. For dependencies, use semver ranges only when a dependency is truly required.

## Plugin packaging checks

- Manifest exists in `.claude-plugin/plugin.json`.
- Manifest JSON parses.
- Referenced component paths exist.
- Component names are kebab-case where user-facing.
- No credentials, secrets, or private project data are bundled.
- Package includes README, usage examples, limitations, and validation notes.
