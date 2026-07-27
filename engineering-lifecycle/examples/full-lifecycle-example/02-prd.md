---
initiative_id: checkout-recovery
skill: create-prd
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - 01-discovery-brief.md
---

# Product Requirements

## Problem

Checkout timeouts leave customers and support without a reliable next action.

## Goals

- Let customers resume a pending checkout or safely start a replacement session.
- Give support a concise view of checkout state without exposing secret provider data.
- Reduce duplicate payment attempts caused by unclear retry behavior.

## Non-Goals
- Changing the payment provider or the provider's own retry behaviour.
- Recovering carts abandoned before checkout was ever started.
- Any change to refund handling.

## Users

- Customer completing a saved cart purchase.
- Support operator reviewing checkout complaints.

## User Stories
- As a customer whose checkout timed out, I want to resume the same session, so that
  I do not re-enter payment details or risk paying twice.
- As a support operator, I want to see the state of a customer's checkout, so that I
  can tell them what happened without asking them to try again blindly.
- As a finance reviewer, I want duplicate attempts to be identifiable, so that I can
  reconcile the provider's settlement file against our orders.

## Functional Requirements

- The cart page must show pending, failed, cancelled, and completed checkout states.
- The system must reuse or safely replace a pending checkout session according to provider idempotency rules.
- Support must see cart ID, checkout status, provider session ID suffix, and last webhook timestamp.
- Customers must see actionable recovery copy for expired or failed sessions.

## Non-Functional Requirements

- Retry behavior must be idempotent.
- Provider secrets and full session payloads must not be stored in customer-visible artifacts.
- Status updates should be observable through logs or metrics.

## Permissions And Data Handling

Support users may view status metadata only. Customers may view only their own cart and checkout state.

## Assumptions
- The provider's session token remains valid for 30 minutes after a timeout. Not yet
  confirmed with the provider; see Open Questions.
- Fewer than 2% of checkouts time out, based on the last 90 days of logs.
- Customers who time out are still authenticated when they return.

## Dependencies

- Provider webhook delivery must be reliable enough to reconcile state. Owned by the
  payments team.
- The audit event schema must land before support tooling can read checkout state.

## Success Metrics

- Duplicate payment attempts per 1,000 checkouts drops from 4.1 to under 1.0 within
  60 days of release.
- At least 70% of timed-out checkouts are resumed rather than restarted.
- Support tickets tagged `checkout-unclear` fall by half against the current baseline
  of 38 per month.

## Acceptance Criteria

- Given a pending session, selecting checkout resumes the existing provider session when it is still valid.
- Given an expired provider session, selecting checkout creates one replacement session and records the reason.
- Given a provider failure, the customer sees a retryable error and support sees the latest failure category.

## Release Criteria
- All acceptance criteria verified in a preview environment against provider sandbox.
- Duplicate-attempt detection verified with a replayed webhook.
- Support view reviewed by two support operators.
- Rollback verified: disabling the feature flag returns the previous behaviour with
  no orphaned sessions.

## Edge Cases

- Webhook arrives after the user starts a replacement checkout.
- Cart contents change while a provider session is pending.
- Provider API returns timeout but later creates a session.

## Out Of Scope

- Multiple payment providers.
- Refund automation.
- Support-side payment mutation actions.

## Open Questions

- [ ] Confirm timeout duration for pending sessions.
- [ ] Confirm provider webhook retry policy.
