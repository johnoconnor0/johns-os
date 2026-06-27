---
name: create-api-contract
description: Use to define REST, RPC, GraphQL, webhook, event, service, frontend-backend, or external integration contracts.
---

# Create API Contract

## Trigger

Use when the user asks for request/response shapes, service boundaries, webhooks, events, auth requirements, pagination, errors, or integration contracts.

## When To Use

- After architecture and data model are sufficiently clear.
- Before implementation planning.
- When multiple components or systems must coordinate.

## Inputs Inspected

- Architecture plan, data model, PRD, and UX flow.
- Existing API routes, schemas, generated clients, webhooks, and integration docs.

## Workflow

1. Inspect upstream artifacts and existing route/schema/client/webhook code before defining new interface behavior.
2. Identify producers, consumers, auth context, compatibility constraints, versioning expectations, and external provider facts.
3. Define endpoints, messages, events, webhooks, request/response shapes, error model, pagination, rate limits, and idempotency where applicable.
4. Mark breaking changes explicitly and provide compatibility or migration notes.
5. Record unknown provider behavior or missing integration documentation as open questions.
6. Validate generated artifacts with `python scripts/validate-artifact.py <artifact paths>`.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/api/api-contract.md`
- `.project/.engineering/initiatives/<initiative-id>/api/openapi-fragment.yaml` when applicable.

## Required Sections

- Purpose
- Consumers
- Endpoints Or Messages
- Request Shape
- Response Shape
- Errors
- Auth And Permissions
- Compatibility
- Open Questions

## Safety Constraints

- Do not invent external provider behavior.
- Version breaking changes explicitly.
- Include auth, error, and compatibility assumptions.

## Related Agents

- `api-contract-reviewer`
- `backend-engineer`
- `frontend-engineer`
- `security-reviewer`
