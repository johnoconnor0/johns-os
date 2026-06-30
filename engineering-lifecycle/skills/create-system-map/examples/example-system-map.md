---
initiative_id: example-checkout
skill: create-system-map
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# System Map: Saved-Cart Checkout

## Product Context

Checkout connects existing cart state to an external payment provider so a
returning shopper can pay for a saved cart. The cart and catalog already exist;
this initiative adds the payment path. The external provider owns card capture
and the hosted payment page, which keeps card data out of our systems.

## Components

- Cart UI: renders the saved cart and exposes the Checkout action.
- Checkout API: creates a provider checkout session for a cart and returns a
  redirect URL.
- Provider adapter: wraps the payment provider SDK and isolates provider
  specifics behind an internal interface.
- Webhook handler: verifies and processes provider payment events, then creates
  or confirms the order.
- Order store: persists orders and the cart-to-order conversion state.

## Data Flow

1. The Cart UI sends the cart ID to the Checkout API.
2. The Checkout API loads the cart, validates it, and asks the provider adapter
   to create a session; the provider returns a session ID and hosted page URL.
3. The user is redirected to the provider's hosted page and pays.
4. The provider sends a signed webhook to the webhook handler.
5. The webhook handler verifies the signature, creates the order from the cart,
   and marks the cart converted (idempotently).
6. The Cart UI polls or is redirected to the order-confirmation screen.

## Missing Information

- The specific payment provider and its webhook signature scheme are not yet
  decided, so the adapter interface is provisional.
- Retry and dead-letter behavior for failed webhook processing needs a
  reliability decision (queue versus synchronous retry).
- Whether order creation must coordinate with an external inventory or
  fulfillment system is unconfirmed.
