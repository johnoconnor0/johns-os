# AI Utilities

Website: https://weblifter.com.au
Repository: https://github.com/johnoconnor0/johns-os

A Claude Code + Codex plugin bundling utility skills for **building and vetting Claude Code
extensions** and for **closing the plan → implementation loop**. It consolidates two former
plugins (`skill-ops` and `plan-review`) into a single `ai-utilities` namespace.

## Skills

### `skill-creator`

```
/ai-utilities:skill-creator [skill-or-plugin-purpose] [--type=skill|plugin|auto] [--update-existing]
```

Create, review, rebuild, validate, and package Claude Code skills or plugins — generates
`SKILL.md`, frontmatter, templates, examples, and supporting files, and can scaffold plugin
agents, hooks, MCP/LSP integrations, and an uploadable extension bundle.

### `skill-review`

```
/ai-utilities:skill-review [path] [--scope=marketplace|plugin|skill|all] [--mode=static|full] [--out=<report-path>]
```

Security, safety, and quality review of a marketplace, plugin, or skill **before install /
approval**. Checks `allowed-tools`/permissions, scans for prompt injection, embedded secrets,
and unsafe tool use, and produces a scored, evidence-backed go/no-go report. Read-only against
the reviewed artifacts.

### `plan-completion-audit`

```
/ai-utilities:plan-completion-audit [path-to-project-root-or-plan-file]
```

Audit a project plan against the actual implementation — verifying code, types, security, and
Supabase backend alignment. Each run writes one timestamped report to
`.project/audits/plan-completion-audit/<YYYY-MM-DD_HHMMSS>.md`.

### `audit-resolver`

```
/ai-utilities:audit-resolver [audit-report-path-or-flags]
```

Read a `plan-completion-audit` report, plan the fixes, and execute them with safety gates per
finding. Verifies between batches and can optionally re-run the audit to confirm closure.
Outputs are written under `.project/audits/audit-resolver/<date>/`.

## Command

### `audit-resolve`

```
/ai-utilities:audit-resolve [report-path | flags]
```

A thin pass-through that dispatches to the `audit-resolver` skill (which owns all confirmation
gates). Discovers the latest report under `.project/audits/` when no path is given, shows the
plan, and asks for confirmation before executing.

## Hooks

- **SessionStart** — prints a one-time summary of the available skills and command.
- **PreToolUse (Write)** — `pre-write-skill.sh` blocks writes to `skill.md` that omit
  `$ARGUMENTS`.
- **PostToolUse (Write|Edit)** — `post-edit-skill.sh` checks skill frontmatter and length;
  `post-edit-script.sh` reminds you to make new script files executable.

## Structure

```text
ai-utilities/
  .claude-plugin/plugin.json      # Claude Code manifest
  .codex-plugin/plugin.json       # Codex manifest + interface
  commands/audit-resolve.md
  hooks/
    hooks.json                    # SessionStart + Pre/PostToolUse wiring
    scripts/                      # welcome, pre-write-skill, post-edit-skill, post-edit-script
  skills/
    skill-creator/
    skill-review/
    plan-completion-audit/
    audit-resolver/
```

## Validation

```bash
python ../scripts/johns-os-marketplace.py validate
```

## Runtime boundaries

- No bundled MCP servers. `plan-completion-audit` uses the user's connected Supabase MCP (or
  the `supabase` CLI) when auditing a Supabase backend; other skills use local tools.
- `skill-review` is read-only against the artifacts it reviews.
- `skill-creator` and `audit-resolver` write files and run local tooling (package managers,
  type checkers, `git`, `zip`). `audit-resolver` applies code fixes only behind explicit
  per-finding confirmation gates.
