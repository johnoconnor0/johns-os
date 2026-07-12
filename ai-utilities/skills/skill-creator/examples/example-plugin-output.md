# Example Plugin Build: software-assurance-audit-program

## What I built

A plugin with profile-first software assurance workflows.

## Structure

```text
software-assurance-audit-program/
  .claude-plugin/plugin.json
  skills/profile-application/SKILL.md
  skills/run-assurance-audit/SKILL.md
  agents/security-auditor.md
  hooks/hooks.json
  references/frameworks/
  scripts/validate_findings.py
```

## Key behaviours

- Profiles the stack before auditing.
- Routes tasks to specialised subagents.
- Uses hooks for read-only guardrails.
- Maps findings to evidence and controls.
- Produces reports, evidence packs, and remediation roadmaps.

## Validation

- JSON/YAML/static structure checks passed.
- Official plugin validation should be run with `claude plugin validate` before publishing.
