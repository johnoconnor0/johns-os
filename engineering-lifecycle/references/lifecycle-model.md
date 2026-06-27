# Lifecycle Model

Engineering Lifecycle uses a canonical product lifecycle. Each stage has a primary skill, expected artifacts, and exit criteria. Stages are sequential by default, but teams may revisit earlier stages when new evidence changes the product or technical shape.

## 1. Discovery

- Purpose: clarify the problem, audience, goals, risks, and MVP boundary.
- Primary skill: `create-discovery-brief`
- Expected inputs: user prompt, stakeholder notes, existing product docs, repo context when available.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/discovery/discovery-brief.md`
- Exit criteria: problem, users, goals, assumptions, risks, and open questions are explicit.
- Recommended next stage: Requirements.

## 2. Requirements

- Purpose: convert discovery into functional, non-functional, and acceptance requirements.
- Primary skill: `create-prd`
- Expected inputs: discovery brief, stakeholder constraints, product context.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/requirements/prd.md`
- Exit criteria: requirements and acceptance criteria are specific enough to plan UX and system behavior.
- Recommended next stage: UX flow.

## 3. UX Flow

- Purpose: map journeys, screens, interaction states, and accessibility considerations.
- Primary skill: `create-ux-flow`
- Expected inputs: PRD, user types, product constraints, existing UI patterns.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/ux/ux-flow.md`, `screen-inventory.md`
- Exit criteria: primary paths, empty/loading/error states, and permission states are defined.
- Recommended next stage: System mapping.

## 4. System Mapping

- Purpose: identify actors, external systems, workflows, components, data flow, boundaries, failures, security, and deployment shape.
- Primary skill: `create-system-map`
- Expected inputs: repo structure, PRD, UX flow, known integrations, deployment notes.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/system-map/system-map.md`
- Exit criteria: core components, responsibilities, interfaces, risks, and missing information are visible.
- Recommended next stage: Architecture.

## 5. Architecture

- Purpose: define implementable technical direction and decision records.
- Primary skill: `create-architecture-plan`
- Expected inputs: system map, constraints, current codebase, operational requirements.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/architecture/architecture-plan.md`, ADR candidates in `.project/.engineering/decisions/`
- Exit criteria: module boundaries, deployment model, major decisions, risks, and tradeoffs are explicit.
- Recommended next stage: Data model.

## 6. Data Model

- Purpose: define entities, relationships, ownership, sensitivity, lifecycle, and migration considerations.
- Primary skill: `create-data-model`
- Expected inputs: architecture plan, PRD, workflows, current schema or storage implementation.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/data/entity-model.md`, `erd.mmd`
- Exit criteria: persistent data shape, ownership, retention, and sensitive data handling are defined.
- Recommended next stage: API/interface contract.

## 7. API/Interface Contract

- Purpose: define boundaries between UI, backend, services, agents, webhooks, events, and external systems.
- Primary skill: `create-api-contract`
- Expected inputs: architecture plan, data model, workflows, integration requirements.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/api/api-contract.md`
- Exit criteria: request/response shapes, errors, auth, events, and compatibility assumptions are clear.
- Recommended next stage: Implementation planning.

## 8. Implementation Planning

- Purpose: sequence the work into safe, reviewable slices.
- Primary skill: `create-implementation-plan`
- Expected inputs: PRD, UX flow, system map, architecture plan, data model, API contract.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/implementation/implementation-plan.md`, `task-breakdown.md`
- Exit criteria: tasks, dependencies, tests, migration steps, and rollback considerations are defined.
- Recommended next stage: Implementation.

## 9. Implementation

- Purpose: execute approved work while respecting repo conventions, tests, and hygiene.
- Primary skill: `implement-feature-safely`
- Expected inputs: accepted implementation plan, codebase, test commands, relevant artifacts.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/implementation/implementation-log.md`
- Exit criteria: intended changes are made, checked, documented, and ready for review.
- Recommended next stage: Review.

## 10. Review

- Purpose: identify correctness, architecture, test, security, migration, and maintainability risks.
- Primary skill: `review-change`
- Expected inputs: diff, branch, PR, implementation plan, relevant artifacts.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/review/change-review.md`
- Exit criteria: findings, residual risks, and required fixes are explicit.
- Recommended next stage: Testing.

## 11. Testing

- Purpose: define and verify appropriate quality coverage.
- Primary skill: `create-test-strategy`
- Expected inputs: implementation plan, diff, PRD, risk profile, existing test suite.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/testing/test-strategy.md`
- Exit criteria: required automated and manual checks are identified and results are recorded.
- Recommended next stage: Release.

## 12. Release

- Purpose: plan rollout, migration, rollback, monitoring, and support.
- Primary skill: `create-release-plan`
- Expected inputs: reviewed change, test strategy, deployment model, operational constraints.
- Expected artifacts: `.project/.engineering/initiatives/<initiative-id>/release/release-plan.md`
- Exit criteria: release steps, rollback path, monitoring, and post-release validation are ready.
- Recommended next stage: Monitoring/maintenance.

## 13. Monitoring/Maintenance

- Purpose: keep the shipped product observable, supportable, and aligned with decisions.
- Primary skill: `build-project-dashboard`
- Expected inputs: lifecycle artifacts, action-item ledger, release notes, monitoring outputs.
- Expected artifacts: `.project/.engineering/dashboards/`, `.project/.engineering/reports/`
- Exit criteria: current state, risks, follow-ups, and decisions are visible.
- Recommended next stage: Repo hygiene.

## 14. Repo Hygiene

- Purpose: keep support files, examples, generated artifacts, and secrets handling consistent.
- Primary skill: `update-repo-hygiene`
- Expected inputs: repo status, env var usage, generated files, docs, package scripts.
- Expected artifacts: `.project/.engineering/hygiene/hygiene-report.md`, `hygiene-report.json`
- Exit criteria: hygiene drift is reported and intentional updates are documented.
- Recommended next stage: return to the relevant lifecycle stage as work continues.
