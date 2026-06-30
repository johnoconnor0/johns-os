---
initiative_id: example-checkout
skill: create-test-strategy
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# Test Strategy

## Coverage

The checkout slice carries payment and order-integrity risk, so it needs unit,
integration, contract, and manual coverage. Load and migration testing are not
required because this initiative adds no schema changes and reuses existing
order tables.

| Layer | Required? | Scope | Risk Covered |
| --- | --- | --- | --- |
| Unit | yes | Stripe adapter: success, validation errors, provider downtime | Incorrect session payloads, unhandled provider faults |
| Integration | yes | `POST /api/checkout/session` against a Stripe test account | Broken end-to-end session creation |
| Contract | yes | Webhook handler validates Stripe signature and event shape | Spoofed or malformed webhook events |
| E2E | yes | Cart to hosted checkout to confirmation in a browser | Redirect and return-URL regressions |
| Regression | yes | Legacy checkout still works with `checkout_v2` off | Flag rollback safety |
| Security | yes | Webhook signature verification and secret handling | Unauthorized order creation |
| Migration | no | No schema or data migration in this initiative | n/a |
| Manual | yes | Exploratory pass on cancellation and timeout paths | Hard-to-automate user recovery flows |

## Scenarios

| Scenario | Given | When | Then |
| --- | --- | --- | --- |
| Happy path session | A valid non-empty cart | User selects checkout | A Stripe session is created and the user is redirected |
| Empty cart guard | An empty cart | User selects checkout | Request is rejected with a clear message, no session created |
| Provider downtime | Stripe returns 503 | User selects checkout | API returns a retryable error and the cart is preserved |
| Webhook idempotency | A `checkout.session.completed` event | The same event is delivered twice | Exactly one order is recorded |
| Invalid webhook signature | A webhook with a bad signature | The handler receives it | The event is rejected with 400 and no order is created |
| Cancelled payment | A created session | User cancels on the Stripe page | User returns to the cart with items intact |

## Manual QA

| Check | Why Manual | Environment |
| --- | --- | --- |
| Cancel flow returns to cart cleanly | Visual and browser back-button behavior is hard to assert in code | Staging |
| Session timeout messaging | Requires waiting out the real provider expiry window | Staging |
| Confirmation email arrives once | Depends on external mail delivery timing | Staging |

## Required Commands

| Command | Required Before | Notes |
| --- | --- | --- |
| `npm run test:unit` | merge | Adapter and handler unit tests |
| `npm run test:integration` | merge | Runs against Stripe test keys |
| `npm run lint` | merge | No new lint errors permitted |
| `npm run test:e2e -- checkout` | release | Browser happy path and cancellation |

## Release Gates

Unit, integration, contract, and lint checks must pass before merge. The E2E
checkout suite and a manual cancellation pass must be green before the 10
percent production step described in the release plan.
