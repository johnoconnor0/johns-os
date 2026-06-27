---
initiative_id: example-initiative
skill: create-implementation-plan
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - ../architecture/architecture-plan.md
---

# Implementation Plan

## Goal

- User-facing outcome:
- Technical outcome:
- Acceptance source:

## Current State

Summarize confirmed current behavior and files/modules likely to change.

## Implementation Slices

1. Slice name: behavior change, files/modules, tests, dependencies, and review boundary.

## Data Or Migration Work

| Change | Risk | Validation | Rollback |
| --- | --- | --- | --- |
| Schema/data/config/backfill item | Risk | Check | Revert/fallback |

## Test Plan

| Check | Command / Method | Required Before |
| --- | --- | --- |
| Unit/integration/manual/release check | Command or QA step | merge/release/post-release |

## Rollback

| Failure | Rollback / Mitigation | Owner |
| --- | --- | --- |
| Failure mode | Disable/revert/fallback step | Owner/unknown |

## Open Questions

- [ ] Resolve unknowns before implementation when they affect correctness.
