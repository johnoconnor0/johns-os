---
name: create-test-strategy
description: Use to define the correct automated and manual test plan for a product, feature, change, migration, release, or risk area.
---

# Create Test Strategy

## Trigger

Use when the user asks what to test, how to verify a feature, which test types are needed, or how to reduce release risk.

## When To Use

- Before or after implementation.
- Before release planning.
- When risk profile or coverage expectations are unclear.

## Inputs Inspected

- PRD, implementation plan, architecture plan, API contract, and current tests.
- Package scripts, CI config, and existing QA docs.

## Workflow

1. Inspect existing tests, package scripts, CI config, risk areas, and acceptance criteria.
2. Classify required coverage by unit, integration, contract, E2E, regression, migration, load, security, and manual QA.
3. Tie every recommended test to a user-facing behavior, failure mode, or implementation slice.
4. Identify which checks are required before merge, before release, and after release.
5. Record unautomated manual QA and why automation is not practical yet.
6. Run `python scripts/validate-artifact.py .project/.engineering/initiatives/<initiative-id>/testing/test-strategy.md`.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/testing/test-strategy.md`

## Required Front Matter

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

## Required Sections

- Coverage
- Scenarios
- Manual QA
- Required Commands
- Release Gates

## Safety Constraints

- Do not claim tests passed unless they were run.
- Scale coverage to risk and blast radius.
- Include manual QA where automation is not practical.

## Related Agents

- `qa-test-strategist`
- `frontend-engineer`
- `backend-engineer`
- `security-reviewer`
