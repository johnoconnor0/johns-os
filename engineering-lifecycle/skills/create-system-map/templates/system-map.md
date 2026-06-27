---
initiative_id: example-initiative
skill: create-system-map
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - none
---

# System Map

## Product Context

Summarize the product, users, and business context confirmed from inspected sources.

## Actors And External Systems

| Actor/System | Type | Responsibility | Evidence |
| --- | --- | --- | --- |
| User, service, vendor, API, IdP, datastore, or ops system | actor / external / internal | Role in workflow | File or source |

## Workflows

| Workflow | Trigger | Components | Data Touched | Failure Point |
| --- | --- | --- | --- | --- |
| Workflow name | Event or user action | Components involved | Entities/events/files | Likely failure |

## Components

| Component | Responsibility | Boundary | Owner / Unknown | Evidence |
| --- | --- | --- | --- | --- |
| Component name | What it owns | Public/internal interface | Owner or unknown | File/source |

## Data Flow

| Data | Source | Destination | Operation | Trust Boundary |
| --- | --- | --- | --- | --- |
| Entity/event/file | Producer | Consumer | read/write/send | Boundary crossed |

## Security And Permissions

| Surface | Auth / Permission | Sensitive Data | Risk |
| --- | --- | --- | --- |
| Route/job/system | Required control | Data class | Failure impact |

## Deployment

| Runtime | Deploy Target | Dependency | Evidence |
| --- | --- | --- | --- |
| App/job/service | Platform/environment | External or internal dependency | File/source |

## Failure Modes

| Failure | Impact | Detection | Mitigation |
| --- | --- | --- | --- |
| Failure point | User/system impact | Log/metric/check | Recovery |

## Missing Information

- [ ] Unknown component, owner, permission, deployment, or integration fact that affects architecture confidence.

## Recommended Next Artifacts

- Architecture plan
- Data model
- API contract
