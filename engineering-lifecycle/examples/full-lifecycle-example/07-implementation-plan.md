---
initiative_id: checkout-recovery
skill: create-engineering-plan
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - 05-architecture-plan.md
  - 06-data-model.md
---

# Implementation Plan

## Goal

Ship checkout recovery behind a feature flag so customers can resume or safely replace timed-out provider sessions.

## Current State

The current checkout flow redirects to a provider but does not expose a durable recovery state in the cart UI or support view.

## Implementation Slices

1. Persistence slice: add `CheckoutSession` storage, status enum, and one-active-session invariant checks.
2. Provider adapter slice: add idempotent create/retrieve behavior and classify provider timeout responses.
3. API slice: add checkout-state and checkout-session endpoints with allowed recovery actions.
4. UI slice: show cart recovery banner and actions for pending, expired, failed, and completed states.
5. Support slice: expose redacted checkout session timeline in support cart detail.

## Data Or Migration Work

Add nullable session fields or a new table first. Backfill is not required unless legacy provider session IDs already exist.

## Test Plan

- Unit test provider timeout classification and idempotency key generation.
- Integration test checkout-state and checkout-session endpoints.
- Contract test webhook status updates.
- Manual QA for customer retry, cancellation, and support view.

## Rollback

Disable the checkout recovery feature flag. Keep persistence tables because they are additive.

## Open Questions

- [ ] Confirm exact migration tool and deployment sequence.
