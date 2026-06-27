---
initiative_id: example-initiative
skill: create-data-model
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - ../architecture/architecture-plan.md
---

# Entity Model

## Entities

| Entity | Purpose | Owner | Source Of Truth |
| --- | --- | --- | --- |
| Entity name | Business/system purpose | Component/team | Storage/system |

## Relationships

| From | Relationship | To | Cardinality | Invariant |
| --- | --- | --- | --- | --- |
| Entity | Relation | Entity | 1:1 / 1:n / n:m | Rule |

## Ownership

| Data | Writer | Reader | Permission |
| --- | --- | --- | --- |
| Entity/field | Component | Component/user | Rule |

## Sensitivity

| Field / Entity | Classification | Handling Rule |
| --- | --- | --- |
| Data item | public/internal/sensitive/secret | Storage/logging/export rule |

## Retention

| Data | Retention | Deletion / Export Rule |
| --- | --- | --- |
| Entity/event | Duration or unknown | Policy |

## Audit And Lifecycle

| Entity | Status Values | Audit Event |
| --- | --- | --- |
| Entity | lifecycle states | Event to record |

## Migration Risk

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Migration/backfill/constraint risk | Impact | Reduction step |

## Open Questions

- [ ] Question that changes schema, ownership, retention, sensitivity, or migration safety.
