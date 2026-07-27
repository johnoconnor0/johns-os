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

## Non-Goals
- Changing how audit events are recorded upstream.
- Exporting anything other than audit events (billing, usage, session logs).
- Scheduled or recurring exports; this release is on-demand only.

## Users

- Returning shoppers with a saved cart who want to complete a purchase.
- Support agents who need to explain checkout failures to customers.
- Finance, who reconcile completed orders against provider payouts.

## User Stories
- As a tenant admin, I want to export a filtered range of audit events, so that I can
  answer a compliance request without asking support for a database extract.
- As a compliance reviewer, I want the export to be provably scoped to one tenant, so
  that I can hand it to an auditor without redacting it first.
- As a support operator, I want to see that an export ran, so that I can tell a
  customer whether their file is on the way.

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

## Assumptions
- Tenants hold fewer than 100,000 audit events per month, based on the current p99.
  Above that the synchronous path will not hold; see Open Questions.
- Admins requesting an export are already authenticated with an unexpired session.
- CSV is acceptable to auditors. Not yet confirmed with a real auditor.

## Dependencies

- The audit event schema must be finalised before the export can select columns.
  Owned by the platform team.
- Object storage lifecycle rules must exist before generated files can be retained.

## Success Metrics

- 60% of tenant admins run at least one export within 30 days of release. Baseline
  is zero: the capability does not exist today.
- Support tickets requesting a manual database extract fall from 12 per month to
  under 2 within one quarter.
- 95% of exports complete within 30 seconds.

## Acceptance Criteria

- Given a valid saved cart, when the user selects Checkout, then they reach the
  provider's hosted payment page with the correct line items and total.
- Given an empty cart, when the user selects Checkout, then they see an
  actionable error and remain on the cart screen.
- Given a confirmed payment webhook, when it is processed twice, then exactly
  one paid order exists for that cart.

## Release Criteria
- All acceptance criteria verified against a tenant with at least 50,000 events.
- Cross-tenant leakage test passes: an export requested by tenant A contains zero
  rows belonging to tenant B.
- Object storage retention rule verified as active before the first real export.
- Rollback verified: disabling the feature flag removes the UI entry point and
  leaves no partially written files.

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
