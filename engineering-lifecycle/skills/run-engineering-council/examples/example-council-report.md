---
initiative_id: example-checkout
skill: run-engineering-council
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - .project/.engineering/initiatives/example-checkout/architecture/architecture-plan.md
---

# Engineering Council Report

## Question

Should checkout use a direct provider integration or a payment orchestration layer?

## Recommendation

Use direct integration for v1 and isolate it behind an adapter.

## Dissent

The expansionist role prefers orchestration if multiple providers are imminent.
