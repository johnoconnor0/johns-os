# Testing Strategy Guide

Testing plans should scale with risk and blast radius.

## Coverage Types

- Unit: isolated logic and edge cases.
- Integration: components, database, services, queues, and filesystem boundaries.
- Contract: API, webhook, event, and schema compatibility.
- E2E: critical user workflows.
- Regression: known breakpoints and changed behavior.
- Migration: schema, data, rollback, and idempotency.
- Security: auth, authorization, secrets, input validation, and sensitive data.
- Manual QA: visual, exploratory, or environment-specific checks that are not practical to automate yet.

## Standards

- Do not claim a test passed unless it was run.
- Tie each check to a behavior, risk, or acceptance criterion.
- Separate required pre-merge checks from release and post-release checks.
- Record residual risk when verification cannot be completed.
