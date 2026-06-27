---
initiative_id: example-initiative
skill: create-api-contract
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - ../architecture/architecture-plan.md
---

# API Contract

## Purpose

- Interface goal:
- Producers:
- Consumers:

## Consumers

| Consumer | Use Case | Compatibility Requirement |
| --- | --- | --- |
| UI/service/webhook/client | Why it calls/receives | Versioning or tolerance |

## Endpoints Or Messages

| Method/Event | Path/Topic | Purpose | Auth |
| --- | --- | --- | --- |
| GET/POST/event | Contract name | Behavior | Required permission |

## Request Shape

```json
{
  "field": "type and meaning"
}
```

## Response Shape

```json
{
  "field": "type and meaning"
}
```

## Errors

| Code / Type | Cause | Client Behavior |
| --- | --- | --- |
| error | trigger | retry/show/block/escalate |

## Auth And Permissions

| Actor | Permission | Data Scope |
| --- | --- | --- |
| Actor/system | Required authz | Tenant/user/resource scope |

## Compatibility

| Change | Breaking? | Migration / Versioning |
| --- | --- | --- |
| Contract change | yes/no | Compatibility plan |

## Open Questions

- [ ] Question that changes wire shape, auth, error handling, idempotency, or compatibility.
