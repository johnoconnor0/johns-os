---
name: update-repo-hygiene
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(python:*)
description: Use to inspect and intentionally update repository hygiene files such as .gitignore, .env.example, docs, changelog, and generated artifact reports.
---

# Update Repo Hygiene

## Trigger

Use when the user asks to update hygiene files, inspect generated files, sync env examples, review ignored files, or clean up repo support artifacts.

## When To Use

- After implementation.
- When new environment variables, generated files, config files, ports, services, or package scripts appear.
- Before release or handoff.

## Inputs Inspected

- Git status when available.
- Env var usage.
- `.env.example`, `.gitignore`, docs, changelog, package scripts, and generated files.
- Hook-generated hygiene reports.

## Workflow

1. Run `python hooks/scripts/detect-new-env-vars.py` and `python hooks/scripts/suggest-gitignore-updates.py`.
2. Inspect `.project/.engineering/hygiene/hygiene-report.json`.
3. Apply `.env.example` additions only when explicitly requested, using placeholders only.
4. Apply `.gitignore` additions only for safe generated/local patterns.
5. Suggest README, CHANGELOG, CLAUDE.md, or Docker ignore changes by default unless the user asked for docs/support-file edits.
6. Write or refresh `.project/.engineering/hygiene/hygiene-report.md`.
7. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/sync-ledger.py"`.

## Outputs

- `.project/.engineering/hygiene/hygiene-report.md`
- `.project/.engineering/hygiene/hygiene-report.json`
- Intentional updates to support files when requested and safe.

## Required Report Sections

- Environment Variables
- Gitignore Candidates
- Support File Updates
- Risks
- Applied Changes

## Safety Constraints

- Never copy secret values into `.env.example`.
- Add variable names with placeholders only.
- Do not ignore source directories or lockfiles unless the project policy says so.
- Suggest docs updates by default unless explicitly asked to edit docs.

## Related Agents

- `repo-hygiene-maintainer`
- `security-reviewer`
- `devops-release-engineer`
