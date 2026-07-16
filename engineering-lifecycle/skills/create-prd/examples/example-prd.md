---
initiative_id: example-checkout
skill: create-prd
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# Product Requirements: Saved-Cart Checkout

## Problem

Customers can add items to a cart and the cart persists across sessions, but
there is no way to pay. Users who return to a saved cart hit a dead end: the
cart screen has no path to payment, so they abandon and the company captures
no revenue from otherwise-ready buyers. Support tickets repeatedly ask "how do
I actually buy this?" and analytics show a high drop-off on the cart screen.

## Goals

- Let a customer move from a saved cart to a hosted payment page in one action.
- Show clear, actionable errors when checkout cannot start (empty cart, expired
  prices, payment provider unavailable).
- Avoid storing any card data in our systems; delegate card capture to the
  payment provider's hosted page.

## Users

- Returning shoppers with a saved cart who want to complete a purchase.
- Support agents who need to explain checkout failures to customers.
- Finance, who reconcile completed orders against provider payouts.

## Functional Requirements

- FR1: From the cart screen, a "Checkout" action creates a checkout session for
  the current cart and redirects the user to the provider's hosted page.
- FR2: The system rejects checkout for an empty cart or a cart whose line-item
  prices have expired, and returns a message naming the reason.
- FR3: On successful payment, an order is created from the cart and the cart is
  marked converted; the user lands on an order-confirmation screen.
- FR4: A provider webhook confirms payment asynchronously; the order is not
  considered paid until the webhook is verified.

## Non-Functional Requirements

- Checkout session creation returns within 800 ms at the 95th percentile.
- Webhook processing is idempotent: a replayed webhook does not create a
  duplicate order or double-confirm an existing one.
- No card numbers, CVCs, or full PANs are ever written to our database or logs.
- Checkout availability target is 99.9% measured monthly.

## Permissions And Data Handling

- Only the authenticated owner of a cart can start checkout for it; a cart is
  never checkoutable by another user.
- Card capture happens solely on the provider's hosted page. We store only the
  provider's session and order identifiers — never card numbers or CVCs.
- Orders and payment records inherit the originating cart's tenant boundary and
  are readable only by that tenant's support and finance roles.

## Acceptance Criteria

- Given a valid saved cart, when the user selects Checkout, then they reach the
  provider's hosted payment page with the correct line items and total.
- Given an empty cart, when the user selects Checkout, then they see an
  actionable error and remain on the cart screen.
- Given a confirmed payment webhook, when it is processed twice, then exactly
  one paid order exists for that cart.

## Edge Cases

- The cart is emptied or an item is removed between opening the cart and
  selecting Checkout: the session is refused with an actionable message.
- The provider webhook arrives before the browser redirect completes: the order
  reconciles exactly once regardless of event ordering.
- The payment provider is unavailable at session creation: checkout fails fast
  with a retry-later message and no partial order is created.

## Out Of Scope

- Stored payment methods and one-click repeat purchases.
- Multi-currency pricing and tax calculation beyond the provider defaults.
- Partial captures, refunds, and subscription billing.

## Open Questions

- Which payment provider is the launch default, and do we need a second
  provider for redundancy at launch?
- What is the price-expiry window before a saved cart must be re-priced?
- Should guest checkout be supported at launch, or only authenticated users?
