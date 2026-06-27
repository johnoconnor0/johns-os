---
initiative_id: example-initiative
skill: create-test-strategy
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - ../implementation/implementation-plan.md
---

# Test Strategy

## Coverage

Define unit, integration, contract, E2E, regression, security, migration, and manual coverage.

| Layer | Required? | Scope | Risk Covered |
| --- | --- | --- | --- |
| Unit/integration/contract/E2E/regression/security/migration/manual | yes/no | Target | Risk |

## Scenarios

| Scenario | Given | When | Then |
| --- | --- | --- | --- |
| Scenario name | Preconditions | Action/event | Expected result |

## Manual QA

| Check | Why Manual | Environment |
| --- | --- | --- |
| Manual check | Reason automation is impractical | Local/staging/prod-like |

## Required Commands

| Command | Required Before | Notes |
| --- | --- | --- |
| Test/lint/typecheck command | merge/release/post-release | Scope |

## Release Gates

Define which checks must pass before rollout.
