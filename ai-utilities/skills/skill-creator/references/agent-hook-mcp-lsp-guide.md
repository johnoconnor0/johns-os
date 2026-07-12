# Agents, hooks, MCP, LSP, monitors, schedules, channels, and programmatic usage

## Agents and subagents

Use agents when a domain specialist should work with its own context window and narrower instructions.

Agent file pattern:

```markdown
---
name: security-auditor
description: Reviews security findings when code, auth, secrets, APIs, or threat models need focused analysis.
model: sonnet
effort: high
tools: Read, Grep, Glob, Bash, Write
---

You are a focused security auditor...
```

Guidelines:

- Give each agent a clear responsibility and output contract.
- Avoid relying on plugin-local hook/MCP settings inside agent frontmatter unless current docs explicitly support it.
- For multi-agent plugins, define an orchestrator and validator.

## Agent teams and agent view

Agent teams are useful for deep parallel work but should be optional. Include a team-mode plan only when:

- the job can be split into independent workstreams;
- the user has enabled the experimental feature;
- write paths are separated to avoid conflicts.

Agent view is useful for monitoring background agents and attaching to long-running sessions. Document it for power users, not as a required path.

## Hooks

Use hooks for deterministic, auditable lifecycle actions:

- `SessionStart`: initialise workspace or load state.
- `PreToolUse`: block dangerous commands or writes.
- `PostToolUse`: validate generated artefacts or record evidence.
- `FileChanged`: mark profiles/states stale.
- `SubagentStop`: collect agent outputs.
- `PreCompact`: snapshot state.
- `Stop`: run final quality checks.

Hooks should be fast, deterministic, and safe. Do not put subjective audit judgement in hooks.

## MCP

MCP servers connect Claude to external tools and resources. For plugin design:

- prefer read-only access during audits and reviews;
- document which operations are mutating;
- include clear server instructions so tool search can discover the right tools;
- degrade gracefully when optional MCPs are absent;
- use local MCPs for plugin-owned generated artefacts only when they add real value.

## MCP Tool Search

For environments with many MCP tools, recommend tool search so tool schemas are discovered on demand. Write concise MCP server descriptions and instructions because they become the routing signal.

## LSP

LSP gives code intelligence such as diagnostics, symbols, definitions, references, and rename context. Treat LSP as optional. Provide `.lsp.json` examples for common stacks but continue with filesystem analysis when unavailable.

## Monitors and channels

Use monitors/channels for event-driven workflows such as CI status, production alerts, security scanner findings, or evidence freshness. Mark research-preview or environment-specific features as optional.

## Goals and prompt schedules

Use goals for bounded loops with clear completion conditions. Use prompt schedules, loops, or routines for recurring reviews such as weekly dependency checks, monthly control evidence reviews, or quarterly assurance audits. Always document whether the run is session-local, cloud-scheduled, or CI-triggered.

## Programmatic usage

For CI/headless use, provide examples using `claude -p` or Agent SDK where applicable. Programmatic flows should:

- specify the plugin path explicitly;
- avoid interactive assumptions;
- write artefacts to deterministic directories;
- produce machine-readable outputs;
- fail closed when evidence is missing.
