---
initiative_id: example-checkout
skill: create-data-model
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# Entity Model: Saved-Cart Checkout

## Entities

- `CheckoutSession`: one attempt to pay for a cart. Fields: `id`, `cart_id`,
  `provider_session_id`, `status` (pending, completed, failed, expired),
  `amount_total`, `currency`, `created_at`, `expires_at`.
- `Order`: a confirmed purchase created from a cart after payment. Fields:
  `id`, `cart_id`, `checkout_session_id`, `provider_payment_id`, `status`
  (paid, refunded), `amount_total`, `currency`, `created_at`.
- `Cart` (existing): gains a `converted_at` timestamp and a nullable
  `order_id`.

## Relationships

- One `Cart` has many `CheckoutSession` rows (a customer may retry checkout).
- One `Cart` has at most one paid `Order`.
- One `Order` references exactly one `CheckoutSession` (the one that paid).
- `provider_session_id` and `provider_payment_id` are unique to support
  idempotent webhook processing.

## Ownership

The checkout service owns `CheckoutSession` and `Order`. The cart service owns
`Cart` and exposes the conversion fields through a defined interface; the
checkout service writes `converted_at` and `order_id` only via that interface,
never by reaching into cart tables directly. No card data is owned by any of
these entities; the payment provider owns card details.

## Sensitivity

No card numbers, CVCs, or full PANs are stored. `provider_session_id` and
`provider_payment_id` are opaque provider references, not secrets, but are
treated as internal. `amount_total` and `currency` are business data, not
personal data. Customer identity lives on the existing cart/customer records
and is referenced, not duplicated here.

## Retention

`CheckoutSession` rows in pending/failed/expired states are retained 90 days
for support and debugging, then purged. `Order` rows are retained 7 years to
meet financial record-keeping requirements, then archived. The `Cart`
conversion fields follow the existing cart retention policy.

## Migration Risk

Low. `CheckoutSession` and `Order` are new tables, so creating them is
non-breaking. The `Cart` change adds two nullable columns (`converted_at`,
`order_id`) with no backfill required, so existing carts remain valid. The
unique constraints on provider IDs must be added before enabling the webhook
handler to guarantee idempotency.
