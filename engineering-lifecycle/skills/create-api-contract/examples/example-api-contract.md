---
initiative_id: example-checkout
skill: create-api-contract
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - .project/.engineering/initiatives/example-checkout/requirements/prd.md
---

# API Contract

## Interface

`POST /api/checkout/session` creates a checkout session.

## Request

Required fields: `cart_id`, `success_url`, `cancel_url`.

## Response

Returns `session_id` and `redirect_url`.

## Errors

Validation errors return `400`; unavailable payment provider returns `503`.
