---
initiative_id: example-checkout
skill: create-test-strategy
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - .project/.engineering/initiatives/example-checkout/implementation/plan.md
---

# Test Strategy

## Unit Tests

Provider adapter handles success, validation errors, and provider downtime.

## Integration Tests

Checkout API creates a session for a valid cart.

## Manual QA

Verify the cart screen redirects to checkout and handles cancellation.
