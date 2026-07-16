---
name: create-release-plan
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*)
description: Use to plan rollout, migration, feature flags, rollback, monitoring, support notes, changelog, and post-release validation.
---

# Create Release Plan

## Trigger

Use when the user asks how to ship, roll out, migrate, monitor, rollback, or prepare support notes for completed work.

## When To Use

- After review and test strategy.
- Before production deployment.
- When release risk, migration, or support coordination matters.

## Inputs Inspected

- Reviewed change, implementation plan, test strategy, deployment model, and operational constraints.
- Existing changelog, runbooks, and release docs.

## Workflow

1. Inspect implementation plan, review findings, test strategy, deployment docs, changelog, runbooks, feature flags, and migration notes.
2. Define release scope, prerequisites, approvals, rollout sequence, monitoring, support handoff, and post-release validation.
3. Identify migration, data, config, dependency, and customer-impact risks.
4. Define rollback or disablement steps that are specific enough to execute.
5. Separate required release gates from optional hardening follow-ups.
6. For a high-risk or hard-to-reverse release, convene `run-engineering-council` before scheduling it.
7. Validate the artifact with `python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" .project/.engineering/initiatives/<initiative-id>/release/release-plan.md`.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/release/release-plan.md`

## Required Sections

- Scope
- Preconditions
- Rollout
- Monitoring
- Rollback
- Support
- Post-Release Validation
- Open Questions

## Safety Constraints

- Do not invent deployment status.
- Include rollback and post-release validation.
- Separate required approvals from optional checks.

## Related Agents

- `devops-release-engineer`
- `qa-test-strategist`
- `security-reviewer`
- `repo-hygiene-maintainer`
