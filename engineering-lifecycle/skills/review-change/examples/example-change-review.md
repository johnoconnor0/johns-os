---
initiative_id: example-checkout
skill: review-change
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - git diff
---

# Change Review

## Findings

No blocking findings in the reviewed checkout API slice.

## Risks

Webhook idempotency should be verified before wider rollout.

## Validation Gaps

No load test evidence was provided.
