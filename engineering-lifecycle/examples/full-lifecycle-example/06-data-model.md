---
initiative_id: checkout-recovery
skill: create-data-model
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - 05-architecture-plan.md
---

# Entity Model

## Entities

- `Cart`: existing purchase container owned by a customer.
- `CheckoutSession`: provider checkout attempt linked to a cart.
- `CheckoutEvent`: optional append-only record of provider and recovery events.

## Relationships

- One cart can have many checkout sessions.
- One checkout session can have many checkout events.
- Only one checkout session should be active for a cart at a time.

## Ownership

Checkout API owns session creation and replacement. Webhook handler owns provider status updates.

## Sensitivity

Store provider session ID, status, expiry, and redacted metadata. Do not store card data, raw webhook secrets, or full provider payloads unless explicitly required and protected.

## Retention

Retain checkout session metadata for support audit windows. Retention duration is unknown and must be confirmed.

## Audit And Lifecycle

Status values: `pending`, `expired`, `cancelled`, `failed`, `completed`, `replaced`.

## Migration Risk

New nullable tables or fields are low risk. Enforcing one active session per cart may require backfill or cleanup if legacy attempts exist.

## Open Questions

- [ ] Confirm whether audit events are required for compliance or only support diagnostics.
