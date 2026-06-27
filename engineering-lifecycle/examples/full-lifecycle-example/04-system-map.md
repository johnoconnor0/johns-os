---
initiative_id: checkout-recovery
skill: create-system-map
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - 02-prd.md
  - 03-ux-flow.md
---

# System Map

## Product Context

Checkout recovery connects cart state, provider checkout sessions, webhook updates, customer messaging, and support visibility.

## Actors And External Systems

- Customer: initiates and resumes checkout.
- Support operator: reads checkout status.
- Payment provider: creates sessions and sends webhook events.
- Application database: stores cart and checkout session records.

## Workflows

- Start checkout: cart UI calls checkout API; API creates or reuses provider session; UI redirects customer.
- Recover checkout: cart UI reads checkout state; API determines whether resume or replacement is allowed.
- Webhook update: provider sends status; webhook handler updates checkout session and cart state.

## Components

- Cart UI.
- Checkout API.
- Payment provider adapter.
- Webhook handler.
- Support cart detail view.
- Checkout session persistence.

## Data Flow

Cart ID and user ID enter the checkout API. The API writes checkout session metadata and receives provider session identifiers. Webhooks update checkout status and timestamps.

## Security And Permissions

Customers can read only their own cart state. Support can read redacted provider metadata. Provider secrets remain server-side only.

## Deployment

Checkout API and webhook handler run in the application backend. Provider webhook configuration must point at the deployed webhook route.

## Failure Modes

- Provider API timeout after session creation.
- Webhook replay or out-of-order delivery.
- Customer retries while a previous session is pending.

## Missing Information

- [ ] Confirm current provider adapter and webhook handler file paths.
- [ ] Confirm data store migration mechanism.

## Recommended Next Artifacts

- Architecture plan.
- Data model.
- API contract.
