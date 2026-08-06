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

Audit a plan against what was actually built. Checks are derived from the plan and the detected
stack rather than run from a fixed list: thirteen families each decide separately whether they
are relevant here and whether they can run, and report one of five outcomes — `passed`,
`failed`, `not-applicable`, `not-checked`, `errored` — where the last three must state a reason.
On a repository with no database there is no data-layer section at all, rather than a phase of
ceremony ending in N/A.

Each run writes one directory, `.project/audits/plan-completion-audit/<YYYY-MM-DD_HHMMSS>/`,
containing `findings.json` and `report.md`.

### `audit-resolver`

```
/ai-utilities:audit-resolver [audit-report-path-or-flags]
```

Read a `plan-completion-audit` run's `findings.json`, plan the fixes, and execute them with
safety gates per finding. Verifies between batches and can optionally re-run the audit to
confirm closure. It reports which check families never ran before it reports anything else:
closing every finding while three families were skipped does not mean the repository is clean.
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
  schemas/findings.schema.json
  scripts/                        # the audit engine, shared by both audit skills
    audit_common.py               #   paths, JSON IO, front matter
    stack_probe.py                #   which stack this is, via a three-rung ladder
    plan_parse.py                 #   the extractor cascade
    families.py                   #   the check-family registry
    checks.py                     #   what each family runs
    findings.py                   #   the findings document and its two hashes
    run-audit.py                  #   the deterministic half of an audit
    render_report.py              #   findings.json -> report.md
    resolver.py                   #   discovery, filtering, legacy conversion
    verify.py                     #   whatever this repo uses to verify itself
  tests/
    test_audit.py
    fixtures/tiny-python-repo/    # the functional eval's target
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

```bash
python -m unittest discover -s ai-utilities/tests
```

## Runtime boundaries

- No bundled MCP servers, and no assumed database. `plan-completion-audit` gates its data-layer
  family on the detected dialect and uses whatever introspection that dialect has; on a
  repository with no database the family reports `not-applicable` with a reason.
- The audit scripts are standalone. `ai-utilities` installs independently of
  `engineering-lifecycle`, so stack detection and the reference checker are reached through a
  ladder — use the real one when it is installed, say so honestly when it is not — rather than
  by importing across plugins, which fails from the plugin cache.
- `skill-review` is read-only against the artifacts it reviews.
- `skill-creator` and `audit-resolver` write files and run local tooling (package managers,
  type checkers, `git`, `zip`). `audit-resolver` applies code fixes only behind explicit
  per-finding confirmation gates.
