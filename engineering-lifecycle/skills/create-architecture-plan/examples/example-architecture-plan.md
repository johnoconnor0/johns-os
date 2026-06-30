---
initiative_id: example-checkout
skill: create-architecture-plan
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# Architecture Plan: Saved-Cart Checkout

## Decision Summary

Introduce a server-side checkout-session boundary that owns all interaction
with the payment provider. The Cart UI never talks to the provider directly;
it calls our Checkout API, which uses a provider adapter to create a session
and returns a hosted-page redirect URL. Payment confirmation arrives only
through a verified provider webhook, and order creation is driven by that
webhook. This keeps catalog reads decoupled from payment writes and keeps card
data entirely inside the provider's hosted page.

The provider adapter is a thin interface (create session, verify webhook,
parse event) so the concrete provider can change without touching callers.
Webhook processing is idempotent and keyed on the provider event ID.

## Alternatives Considered

- Client-side provider SDK: the browser creates the session directly with the
  provider. Rejected because it leaks provider keys handling to the client,
  spreads provider logic across the frontend, and makes server-side validation
  of cart state harder.
- Synchronous payment confirmation in the redirect callback only: trust the
  browser return URL to mark the order paid. Rejected because the return is not
  reliable (users close tabs) and is spoofable; the webhook is the source of
  truth.
- Polling the provider for payment status on a timer: rejected as more costly
  and higher latency than a verified webhook, and it still needs idempotency.

## Risks

- Webhook retries and out-of-order delivery can create duplicate orders.
  Mitigation: idempotency keyed on provider event ID plus a unique constraint
  on cart-to-order conversion.
- Provider outage blocks checkout entirely. Mitigation: feature flag to disable
  checkout gracefully and a clear user-facing error, with an adapter interface
  that allows a second provider later.
- Price drift between cart creation and payment. Mitigation: re-validate
  line-item prices at session creation and reject expired carts.

## Validation

Contract tests cover session creation (valid, empty, and expired carts) and
webhook handling (first delivery, duplicate delivery, invalid signature). An
integration test exercises the full redirect-and-webhook path against the
provider sandbox before launch.
