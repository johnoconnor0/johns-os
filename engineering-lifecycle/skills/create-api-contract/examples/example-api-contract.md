---
initiative_id: example-checkout
skill: create-api-contract
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# API Contract: Saved-Cart Checkout

## Purpose

Define the server-side checkout endpoint that turns a saved cart into a
provider checkout session, plus the provider webhook our service consumes to
confirm payment. This contract isolates the Cart UI and the payment provider
from each other so neither depends on the other's internals.

## Consumers

- Cart UI (first-party web client): calls `POST /api/checkout/session` to start
  checkout and uses the returned redirect URL.
- Payment provider (external): calls our `POST /api/checkout/webhook` endpoint
  to deliver signed payment events.
- Order-confirmation screen: reads order status via the existing orders API
  after redirect.

## Endpoints Or Messages

- `POST /api/checkout/session` — create a checkout session for a cart
  (authenticated first-party caller).
- `POST /api/checkout/webhook` — receive provider payment events (authenticated
  by signature header, not by user session).

## Request Shape

`POST /api/checkout/session`

```json
{
  "cart_id": "cart_9f3a",
  "success_url": "https://shop.example.com/checkout/success",
  "cancel_url": "https://shop.example.com/cart"
}
```

Required fields: `cart_id`, `success_url`, `cancel_url`. The webhook request
body is the provider's event payload, verified against the
`X-Provider-Signature` header before parsing.

## Response Shape

`201 Created` from `POST /api/checkout/session`:

```json
{
  "session_id": "cs_a1b2c3",
  "redirect_url": "https://pay.provider.com/session/cs_a1b2c3",
  "expires_at": "2026-01-01T00:30:00Z"
}
```

The webhook endpoint returns `200 OK` with an empty body once the event is
accepted (or recognized as a duplicate and ignored).

## Errors

- `400 Bad Request`: missing or malformed `cart_id`, `success_url`, or
  `cancel_url`.
- `409 Conflict`: cart is empty or its prices have expired; body includes a
  `reason` field (`empty_cart`, `prices_expired`).
- `401 Unauthorized`: webhook signature verification fails.
- `503 Service Unavailable`: payment provider is unreachable; the caller should
  retry with backoff.

## Compatibility

The session endpoint is versioned under `/api`. New optional request fields may
be added without a version bump; removing or renaming fields, or changing error
codes, requires a new version. The webhook handler tolerates unknown event
types by acknowledging and ignoring them, so provider additions do not break
us. Idempotency is keyed on the provider event ID.

## Open Questions

- Should `success_url` and `cancel_url` be validated against an allowlist to
  prevent open-redirect abuse?
- What backoff and retry schedule does the provider use for webhook delivery,
  and how long must we retain processed event IDs for deduplication?
- Do we need a synchronous `GET /api/checkout/session/{id}` for the UI to poll
  status, or is the redirect plus orders API sufficient?
