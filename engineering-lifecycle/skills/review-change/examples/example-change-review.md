---
initiative_id: example-checkout
skill: review-change
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# Change Review

## Findings

| Severity | File / Area | Issue | Evidence | Recommendation |
| --- | --- | --- | --- | --- |
| P1 | api/checkout/webhook.ts | Webhook handler does not deduplicate on event id, so a retried event can create a second order | Handler inserts an order without checking `event.id`, observed in the integration test for duplicate delivery | Store processed event ids and skip already-seen events |
| P2 | api/checkout/session.ts | Provider 5xx responses surface as a generic 500 with no retry hint | Stripe 503 mapped to `throw new Error("checkout failed")` | Return a 502 with a retryable error code so the cart can offer retry |
| P3 | api/checkout/session.ts | Magic string `"checkout_v2"` repeated for the flag check | Flag name appears in three call sites | Extract a `CHECKOUT_V2_FLAG` constant |
| P3 | web/cart/CartScreen.tsx | Checkout button is not disabled during session creation | No loading guard around the click handler | Disable while the request is in flight to prevent double submits |

## Tests

Tests run:

| Command / Scenario | Result | Notes |
| --- | --- | --- |
| `npm run test:unit` | passed | Adapter and handler units green |
| `npm run test:integration` | passed | Includes the duplicate-webhook case that surfaced the P1 |
| `npm run lint` | passed | No new lint errors |
| `npm run test:e2e -- checkout` | not run | E2E suite not exercised in this review pass |

Recommended tests:

| Check | Reason |
| --- | --- |
| Idempotency regression after the P1 fix | Confirm a retried event creates exactly one order |
| E2E cancellation path | Verify cart is preserved when the shopper cancels |

## Residual Risk

- Unverified area: End-to-end browser flow under real provider latency.
- Reason: The E2E checkout suite was not run during this review.
- Impact: A redirect or return-URL regression could reach the 10 percent rollout undetected.

## Open Questions

- [ ] Is the P1 idempotency fix required before merge, or acceptable to land behind the off flag with a fast follow?
