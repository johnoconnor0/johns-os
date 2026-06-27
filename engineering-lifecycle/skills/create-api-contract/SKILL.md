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

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/api/api-contract.md`
- `.project/.engineering/initiatives/<initiative-id>/api/openapi-fragment.yaml` when applicable.

## Safety Constraints

- Do not invent external provider behavior.
- Version breaking changes explicitly.
- Include auth, error, and compatibility assumptions.

## Related Agents

- `api-contract-reviewer`
- `backend-engineer`
- `frontend-engineer`
- `security-reviewer`
