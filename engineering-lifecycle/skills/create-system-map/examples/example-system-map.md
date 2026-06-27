---
initiative_id: example-checkout
skill: create-system-map
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - .project/.engineering/initiatives/example-checkout/requirements/prd.md
---

# System Map

## Product Context

Checkout connects cart state to an external payment provider.

## Components

Cart UI, checkout API, provider adapter, webhook handler.

## Data Flow

Cart ID enters the API, provider session is created, webhook confirms payment.
