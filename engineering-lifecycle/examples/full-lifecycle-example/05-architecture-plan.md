---
initiative_id: checkout-recovery
skill: create-architecture-plan
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - 04-system-map.md
---

# Architecture Plan

## Decision Summary

Add a server-side `CheckoutSession` boundary between carts and the payment provider. The checkout API owns idempotency and recovery decisions; the UI only renders state and actions returned by the API.

## Constraints

- Provider secrets must remain server-side.
- Recovery behavior must avoid duplicate payable sessions.
- Support visibility must use redacted provider metadata.

## Recommended Architecture

- Checkout API exposes `GET /cart/:id/checkout-state` and `POST /cart/:id/checkout-session`.
- Provider adapter hides provider-specific session and webhook behavior.
- Webhook handler updates `CheckoutSession` status idempotently.
- Support view reads the same status model as customer recovery, with additional redacted metadata.

## Interfaces And Boundaries

The UI never decides whether to reuse or replace a session. The backend returns allowed actions such as `resume`, `replace`, `retry_later`, or `contact_support`.

## Alternatives Considered

- Client-side provider session reuse: rejected because it exposes too much provider behavior to the UI.
- Payment orchestration layer: deferred because the MVP has one provider.

## Risks

- Provider timeout semantics may differ from assumptions.
- Webhook ordering may require version or timestamp checks.

## Migration And Rollback

Add nullable checkout session fields first. Roll back by disabling recovery actions and returning the previous checkout flow.

## ADR Candidates

- [ ] ADR: Own checkout recovery through a server-side session boundary.
