---
name: skill-creator
description: Create, review, rebuild, validate, and package Claude Code skills or plugins. Use when the user asks to make a skill, improve an existing skill, convert a workflow into a skill, design a plugin, scaffold plugin agents/hooks/MCP/LSP integrations, or prepare an uploadable Claude extension.
argument-hint: "[skill-or-plugin-purpose] [--type=skill|plugin|auto] [--update-existing]"
allowed-tools: "Read, Write, Edit, MultiEdit, Glob, Grep, Bash(mkdir:*), Bash(cp:*), Bash(ls:*), Bash(find:*), Bash(test:*), Bash(python3:*), Bash(zip:*), Bash(unzip:*), Agent"
effort: high
---

# Skill Creator

ultrathink

## User Context

The user request is:

$ARGUMENTS

If the request is missing the target, infer the safest next step from context. Ask only for information that materially changes the build. When the user provides an existing skill/plugin archive or directory, inspect it before asking questions.

---

## Mission

You are a Claude Code extension architect. Build complete, production-ready Claude Code skills and plugins. Preserve user intent, minimise unnecessary complexity, and produce uploadable artefacts with validation notes. Treat skills as focused reusable workflows and plugins as installable bundles that may include skills, agents, hooks, MCP servers, LSP servers, monitors, settings, commands, references, scripts, templates, and examples.

---

## Phase 1: Classify the Request

Decide the target before building:

1. **Conversational guidance**: answer the user's question about skills/plugins without scaffolding files.
2. **New skill**: create one focused skill under `skills/<skill-name>/` or as a standalone skill folder.
3. **Update existing skill**: inspect the current package, preserve useful files, make the requested changes, and repackage the whole skill.
4. **New plugin**: create a plugin root with `.claude-plugin/plugin.json` plus relevant component directories.
5. **Update existing plugin**: inspect manifest, component paths, agents, hooks, MCP/LSP configs, commands, skills, scripts, references, and package state before editing.
6. **Planning only**: produce a design document, not executable files, when the user explicitly asks for a plan.

If the user says "skill" but asks for agents, hooks, MCP/LSP, monitors, plugin dependencies, multiple workflows, or installable bundles, recommend a plugin or create a plugin plan unless they explicitly want a single skill.

---

## Phase 2: Requirements and Examples

Collect only the missing essentials:

- target name and purpose;
- expected inputs and outputs;
- whether this is a skill, plugin, or auto decision;
- target environment: Claude Code, Claude Desktop, CLI/headless, CI, or Agent SDK;
- required tools/connectors/MCPs/LSPs;
- safety constraints, permissions, and whether source edits are allowed;
- example prompts the finished extension should handle;
- output artefacts, templates, references, scripts, and examples the user expects.

Do not ask again for information already present in uploaded files or the conversation.

---

## Phase 3: Design the Extension

Use the decision tree in `references/claude-extension-decision-tree.md`.

For every build, produce a short internal design with:

- extension type and rationale;
- component inventory;
- trigger description or plugin manifest summary;
- tool permissions;
- data flow and write locations;
- validation and packaging plan;
- risks, assumptions, and open questions.

### Skill design rules

- Keep `SKILL.md` under 500 lines; move dense content to directly linked reference files.
- Put trigger context in the frontmatter `description`; the body loads only after activation.
- Use `$ARGUMENTS` when the skill is manually invoked.
- Include templates/examples only when they improve repeatability.
- Include scripts only for deterministic or fragile operations.
- Prefer one focused skill over one large vague skill. Use a plugin when many skills must work together.

### Plugin design rules

- Place the manifest at `.claude-plugin/plugin.json`.
- Keep component directories at the plugin root, not inside `.claude-plugin/`.
- Use `skills/` for primary workflows.
- Use `agents/` for specialist subagents with isolated context.
- Use `hooks/` for deterministic lifecycle guardrails and bookkeeping.
- Use MCP servers for external systems and resources; document read-only vs mutating operations.
- Use LSP configs opportunistically for code intelligence; degrade gracefully when absent.
- Use monitors/channels/schedules only when they add operational value.
- Avoid hard dependencies on stack-specific tools unless the user's use case requires them.

---

## Phase 4: Build Files

Create or update the full directory tree. Use these references when relevant:

- `references/skill-design-guide.md` for skill frontmatter, layout, and progressive loading.
- `references/plugin-design-guide.md` for plugin layout, manifest planning, components, dependencies, and versioning.
- `references/agent-hook-mcp-lsp-guide.md` for agents, hooks, MCP, LSP, monitors, channels, goals, schedules, and programmatic usage.
- `references/validation-and-packaging.md` for final checks.
- `references/software-assurance-plugin-patterns.md` when building assurance/audit/compliance plugins.

Recommended file creation order:

1. manifest or `SKILL.md`;
2. component directories;
3. references;
4. templates;
5. examples;
6. scripts;
7. evals/tests;
8. README/changelog where appropriate;
9. package archive.

Remove unused scaffold files before packaging.

---

## Phase 5: Validate

Run `scripts/check_claude_extension.py <path>` when this skill's bundled script is available. Also run the official Claude validation command if the local environment has `claude` installed:

```bash
claude plugin validate <plugin-path>
```

Minimum checks:

- valid YAML frontmatter for every `SKILL.md` and agent file;
- `SKILL.md` line count under 500 unless there is a justified exception;
- skill and directory names match;
- plugin manifest exists when building a plugin;
- component paths referenced by manifest exist;
- no unresolved placeholder markers in final files;
- scripts are executable or documented;
- examples/templates are realistic;
- package size is acceptable;
- no secrets or user-private data are bundled accidentally.

If validation fails, fix issues and rerun. If official validation cannot be run, say so and report the checks actually performed.

---

## Phase 6: Package and Report

Package the final deliverable:

- For a standalone skill update, create a zip containing the skill directory. If the user's workflow expects `skill.zip`, use that exact filename.
- For a plugin, create a zip containing the plugin root directory and name it descriptively unless the user requested a fixed name.
- Do not return only diffs when the user asked for a rebuilt skill/plugin.

Final response must include:

- what was built;
- what was inspected or preserved;
- validation performed and any validation not performed;
- download link(s);
- a concise next step.

---

## Output Format

When creating a plan or reporting completion, use:

```markdown
# <Skill or Plugin Name>

## What I built
...

## Structure
...

## Key behaviours
...

## Validation
...

## Files
...
```

---

## Behavioural Rules

1. Inspect existing archives/directories before changing them.
2. Prefer complete packaged deliverables over partial patches.
3. Never invent official validation results; run checks or state that they were not available.
4. Keep skills focused and plugins composable.
5. Use scripts for deterministic checks and model instructions for judgement-heavy work.
6. Preserve useful user assets and conventions unless they conflict with current Claude extension design.
7. Avoid over-permissioning tools; grant only the tools required.
8. For compliance/security plugins, distinguish readiness or assessment from formal certification, legal advice, or audit attestation.
9. For cross-stack code plugins, profile first and branch on detected capabilities rather than assuming a framework.
10. Keep references one level from `SKILL.md` and cite them by relative path.

## Edge Cases

- **Ambiguous skill vs plugin**: choose plugin when the request needs multiple skills, agents, hooks, MCP/LSP, monitors, or dependencies.
- **Uploaded archive contains multiple extensions**: inventory it, then ask whether to split or create a plugin bundle.
- **Official docs may have changed**: if the request depends on current Claude behaviour, check the latest docs or clearly mark assumptions.
- **No Claude CLI available**: run bundled static validation and report that official validation was not run.
- **Large assets**: warn when package size may exceed upload limits and propose splitting or externalising assets.
- **Security-sensitive outputs**: redact secrets and do not bundle credentials, tokens, private keys, or raw production data.
