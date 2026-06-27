---
name: review-change
description: Use to review a branch, pull request, diff, or uncommitted change for correctness, architecture, security, tests, migrations, and maintainability.
---

# Review Change

## Trigger

Use when the user asks for a code review, PR review, diff review, architecture review of changes, or risk assessment.

## When To Use

- Before merge or release.
- After implementation.
- When a change touches shared behavior, security, data, or deployment.

## Inputs Inspected

- Git diff, PR context, or changed files.
- Implementation plan and relevant lifecycle artifacts.
- Tests and existing conventions.

## Workflow

1. Inspect the actual diff or changed files before making claims.
2. Compare behavior against the implementation plan, architecture decisions, and test strategy where available.
3. Review correctness, security, data/migration impact, API compatibility, operational risk, and maintainability.
4. Put findings first, ordered by severity, with concrete file references.
5. State tests actually run separately from recommended tests.
6. Write the review artifact and validate it with `python scripts/validate-artifact.py <review artifact>`.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/review/change-review.md`

## Required Front Matter

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

## Required Sections

- Findings
- Tests
- Residual Risk
- Open Questions

## Safety Constraints

- Findings first, ordered by severity.
- Cite concrete files and evidence.
- Do not invent test results.
- Mark residual risk when checks cannot be run.

## Related Agents

- `solution-architect`
- `security-reviewer`
- `qa-test-strategist`
- `repo-hygiene-maintainer`
