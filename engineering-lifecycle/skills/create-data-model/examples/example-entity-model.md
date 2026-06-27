---
initiative_id: example-checkout
skill: create-data-model
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - .project/.engineering/initiatives/example-checkout/requirements/prd.md
---

# Entity Model

## Entities

`CheckoutSession` belongs to `Cart` and records provider session IDs.

## Relationships

One cart can have many checkout attempts.

## Sensitivity

Do not store card data.

## Migration Risk

Backfill is not required for a new nullable table.
