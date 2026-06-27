---
name: create-release-plan
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

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/release/release-plan.md`

## Safety Constraints

- Do not invent deployment status.
- Include rollback and post-release validation.
- Separate required approvals from optional checks.

## Related Agents

- `devops-release-engineer`
- `qa-test-strategist`
- `security-reviewer`
- `repo-hygiene-maintainer`
