---
initiative_id: checkout-recovery
skill: create-discovery-brief
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - README.md
  - none
---

# Discovery Brief

## Problem

Returning customers abandon carts when a payment provider timeout leaves the cart in an uncertain state. Support currently asks customers to refresh and retry, but the product does not explain whether payment was created, failed, or still pending.

## Users

- Returning customer with a saved cart.
- Support operator investigating checkout complaints.
- Operations owner watching payment webhook health.

## Evidence

- User-supplied support notes list repeated "charged but no order" complaints.
- README-style product context describes checkout as a provider redirect flow.
- No inspected artifact currently defines retry, cancellation, or timeout behavior.

## Goals And Success Signals

- Customers can safely resume or cancel a timed-out checkout.
- Support can see the latest checkout session state.
- Checkout timeout tickets decline after rollout.

## Assumptions

- The payment provider supports idempotent checkout session creation.
- Existing cart records can store a provider session identifier.

## Risks

- Incorrect retry behavior could create duplicate provider sessions.
- Support visibility may require exposing payment state carefully.

## MVP Boundary

Include checkout session retry, cancellation messaging, and support-visible status. Exclude multi-provider routing and automatic refunds.

## Open Questions

- [ ] Confirm provider idempotency key requirements.
- [ ] Confirm which payment states support can view.

## Recommended Next Artifact

Create a PRD focused on retry behavior, customer messaging, and support visibility.
