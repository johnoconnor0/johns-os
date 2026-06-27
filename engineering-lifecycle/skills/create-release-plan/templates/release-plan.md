---
initiative_id: example-initiative
skill: create-release-plan
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - ../testing/test-strategy.md
---

# Release Plan

## Scope

| Item | Included? | Notes |
| --- | --- | --- |
| Feature/change/migration | yes/no | Boundary |

## Preconditions

| Precondition | Owner | Evidence |
| --- | --- | --- |
| Required state | Owner/unknown | Check/source |

## Rollout

| Step | Audience / Environment | Gate |
| --- | --- | --- |
| 1 | Internal/staging/percentage | Metric or approval |

## Monitoring

| Signal | Threshold | Response |
| --- | --- | --- |
| Metric/log/ticket | Healthy/unhealthy | Action |

## Rollback

| Failure | Rollback Step | Validation |
| --- | --- | --- |
| Failure mode | Disable/revert/fallback | Check |

## Support

| Audience | Note | Owner |
| --- | --- | --- |
| Support/customer/internal | Required communication | Owner |

## Post-Release Validation

| Check | Timing | Owner |
| --- | --- | --- |
| Validation | After rollout window | Owner |

## Open Questions

- [ ] Confirm release readiness gaps.
