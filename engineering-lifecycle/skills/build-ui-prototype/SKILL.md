---
name: build-ui-prototype
description: Use when the user asks to build a lightweight UI prototype, clickable MVP, app shell, dashboard mock, product demo, or frontend proof-of-concept from requirements, UX flows, screen inventory, or an implementation plan.
---

# Build UI Prototype

## Trigger

Use when the user explicitly asks to build, create, implement, prototype, scaffold, or demo a user-facing UI, MVP shell, dashboard, clickable flow, app screen, or frontend proof-of-concept.

## When To Use

- Use after a PRD, UX flow, screen inventory, or implementation plan exists.
- Use when the user wants source changes, not only planning.
- Use when mock data is acceptable or explicitly requested.
- Use when a lightweight vertical slice is more useful than full production implementation.
- Use when a demoable product experience is needed quickly.

## When Not To Use

- Use `create-discovery-brief` when the product idea is unclear.
- Use `create-prd` when requirements are missing.
- Use `create-ux-flow` when screens and states are not defined.
- Use `create-architecture-plan` when architecture decisions are unresolved.
- Use `implement-feature-safely` for general non-UI implementation work.
- Use `review-change` after the prototype is implemented.

## Inputs

Inspect available inputs before editing:

- PRD, discovery brief, UX flow, and screen inventory.
- Implementation plan when available.
- Existing routes, pages, layouts, components, styling, design-system conventions, and mock data patterns.
- Package scripts, test commands, framework config, and README.
- Relevant `.project/.engineering` artefacts and hygiene reports.

Look for these initiative artefacts when an initiative ID or `.project/.engineering` workflow is present:

- `.project/.engineering/initiatives/<initiative-id>/requirements/prd.md`
- `.project/.engineering/initiatives/<initiative-id>/ux/ux-flow.md`
- `.project/.engineering/initiatives/<initiative-id>/ux/screen-inventory.md`
- `.project/.engineering/initiatives/<initiative-id>/system-map/system-map.md`
- `.project/.engineering/initiatives/<initiative-id>/architecture/architecture-plan.md`
- `.project/.engineering/initiatives/<initiative-id>/implementation/implementation-plan.md`

Inspect the repo for:

- `package.json`
- `README.md`
- Existing routes, pages, or app directory
- Existing components and layouts
- Styling, theme, and design-system files
- Test setup and package scripts
- Mock data or fixture conventions
- `.env.example`
- Framework config

## Prototype Modes

Classify the request before editing:

- Static UI mock: visual or interaction exploration when no API or data model exists.
- Clickable prototype: demoable flow with navigation, forms, modals, fake transitions, local state, and mock data.
- Vertical MVP slice: one thin working journey when a basic backend or data contract already exists.
- Dashboard/app shell: SaaS shell, navigation, cards, tables, empty states, placeholder data, and responsive layout.

## Workflow

1. Confirm implementation intent. If the request only asks to plan, design, or map, produce a prototype plan but do not edit source. If intent is unclear, ask whether to plan only, build a prototype with mock data, or build a thin MVP slice using existing APIs/data.
2. Inspect upstream artefacts and current UI conventions before proposing files or components.
3. Classify the prototype mode as static UI mock, clickable prototype, vertical MVP slice, or dashboard/app shell.
4. Define the smallest useful user journey and screen set that demonstrates the product value. Do not build every screen.
5. State planned files/components, data strategy, mocked behaviour, validation commands, and known limitations before editing.
6. Implement the prototype in small scoped changes using existing project conventions.
7. Prefer mock data unless real APIs, schemas, and permissions are already approved.
8. Include empty, loading, error, success, and permission states where relevant.
9. Run the smallest relevant validation commands available from package scripts.
10. Write prototype plan, implementation log, QA checklist, and limitations artefacts when an initiative path exists or can be inferred.
11. Record follow-up work for productionisation.

## Scope Statement

Before editing, produce a short scope statement:

```markdown
## Prototype Scope

- Prototype mode:
- User journey:
- Screens included:
- Screens excluded:
- Data source:
- Mocked behaviour:
- Real behaviour:
- Known limitations:
- Validation commands:
```

## File Plan

Before editing, map screens to files/components:

```markdown
## Planned Files

| File | Purpose | New / Existing | Risk |
| --- | --- | --- | --- |
| app/dashboard/page.tsx | Dashboard prototype route | New | Low |
| components/prototype/audit-card.tsx | Display mock audit status | New | Low |
| lib/prototype/mock-audit-data.ts | Mock data source | New | Low |
```

Adapt file paths to the detected framework.

## Implementation Rules

- Use existing conventions.
- Keep changes small.
- Prefer mock data unless APIs are already defined.
- Do not invent real integrations.
- Do not add unnecessary dependencies.
- Do not change core architecture unless explicitly requested.
- Do not touch production auth, billing, payment, database, or production config code unless needed and approved.
- Include empty, loading, error, success, and permission states where practical.
- Keep accessibility basic but explicit.
- Preserve responsive behaviour.
- Keep prototype limitations visible.

## Safety Constraints

- Do not build without clear implementation intent.
- Do not invent real backend, API, or provider behaviour.
- Do not represent mock data as production data.
- Do not add unnecessary dependencies.
- Do not edit auth, billing, payment, database, production config, or sensitive permission code unless explicitly requested and scoped.
- Do not claim production readiness unless tests, review, security, and release criteria support it.

## Prototype Artefacts

When an initiative ID exists or can be inferred, write:

- `.project/.engineering/initiatives/<initiative-id>/prototype/prototype-plan.md`
- `.project/.engineering/initiatives/<initiative-id>/prototype/prototype-implementation-log.md`
- `.project/.engineering/initiatives/<initiative-id>/prototype/prototype-qa-checklist.md`
- `.project/.engineering/initiatives/<initiative-id>/prototype/prototype-limitations.md`

Use the files in `templates/` for these artefacts. The limitations file is required to prevent the prototype from being mistaken for production-ready software.

If no initiative path exists, still summarize plan, implementation log, QA checklist, and limitations in the final response or place them in the nearest project documentation location only when consistent with repo conventions.

## Outputs

- Source changes for the UI prototype when explicitly requested.
- `.project/.engineering/initiatives/<initiative-id>/prototype/prototype-plan.md`
- `.project/.engineering/initiatives/<initiative-id>/prototype/prototype-implementation-log.md`
- `.project/.engineering/initiatives/<initiative-id>/prototype/prototype-qa-checklist.md`
- `.project/.engineering/initiatives/<initiative-id>/prototype/prototype-limitations.md`

## Lifecycle Position

Use this skill as the implementation bridge in the product workflow:

```text
create-discovery-brief
-> create-prd
-> create-ux-flow
-> build-ui-prototype
-> create-test-strategy
-> review-change
-> create-release-plan
```

For a more technical MVP:

```text
profile-product-system
-> create-discovery-brief
-> create-prd
-> create-ux-flow
-> create-system-map
-> create-architecture-plan
-> create-data-model
-> create-api-contract
-> create-implementation-plan
-> build-ui-prototype
-> implement-feature-safely
-> create-test-strategy
-> review-change
-> create-release-plan
```

Keep the boundary clear: `build-ui-prototype` is for a user-facing prototype or MVP UI slice; `implement-feature-safely` is for broader implementation beyond the prototype.

## References

- Read `engineering-lifecycle/references/prototype-scope-guide.md` when choosing prototype mode, included screens, excluded screens, and data strategy.
- Read `engineering-lifecycle/references/ui-state-coverage-guide.md` when deciding empty, loading, error, success, permission, responsive, and accessibility states.
- Use `examples/` for realistic invocation patterns and expected output shape.

## Validation

Inspect `package.json` before choosing commands. Run the smallest relevant checks available, such as:

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `pnpm lint`
- `pnpm typecheck`
- `pnpm test`
- `npm run build`

If no test/build commands exist, state that clearly and provide manual QA steps.

## Final Response

Include these sections:

- Prototype Built
- Files Changed
- Screens / Flow Included
- Mocked vs Real Behaviour
- Validation Run
- Known Limitations
- Recommended Next Steps

Never claim the prototype is production-ready unless release, test, security, and review checks actually support that.

## Related Agents

- `ux-flow-designer`
- `frontend-engineer`
- `requirements-analyst`
- `qa-test-strategist`
- `repo-hygiene-maintainer`
- `solution-architect` when architecture changes are involved
- `backend-engineer` when backend/API work is involved
- `security-reviewer` when permissions, PII, account data, or auth flows are involved
