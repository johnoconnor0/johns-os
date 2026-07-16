---
name: create-design-system
allowed-tools: Read, Grep, Glob, Write, Edit
description: Use when the user asks to plan, document, create, audit, or implement a design system, UI kit, component system, design tokens, typography, colours, spacing, accessibility rules, or reusable frontend component standards.
---

# Create Design System

## Trigger

Use when the user asks for a design system, UI kit, component library, visual language, design tokens, frontend UI standards, component inventory, typography system, colour system, spacing system, accessibility rules, or reusable interface guidelines.

## When To Use

- After product requirements or UX flows are clear enough.
- Before building UI prototypes or MVP screens.
- When an existing app has inconsistent UI patterns.
- When frontend implementation needs reusable component standards.
- When design tokens, components, states, or accessibility rules need to be documented.
- When a prototype needs a consistent visual system.

## When Not To Use

- Use `create-discovery-brief` when the product idea is unclear.
- Use `create-prd` when requirements are missing.
- Use `create-ux-flow` when user journeys and screens are missing.
- Use `build-ui-prototype` when the user wants code for a clickable UI prototype.
- Use `create-architecture-plan` when the user wants broad architecture planning.
- Use `review-change` when the user wants a completed UI change reviewed.

## Inputs Inspected

Inspect available inputs before creating design-system claims:

- Product profile.
- Discovery brief.
- PRD.
- UX flow.
- Screen inventory.
- Prototype plan when available.
- Existing routes, pages, layouts, components, styling, tokens, and design conventions.
- Package scripts and frontend framework configuration.
- Existing design assets or brand notes if provided.

Look for these initiative and profile artefacts when present:

- `.project/.engineering/profile/product-system-profile.yaml`
- `.project/.engineering/initiatives/<initiative-id>/discovery/discovery-brief.md`
- `.project/.engineering/initiatives/<initiative-id>/requirements/prd.md`
- `.project/.engineering/initiatives/<initiative-id>/ux/ux-flow.md`
- `.project/.engineering/initiatives/<initiative-id>/ux/screen-inventory.md`
- `.project/.engineering/initiatives/<initiative-id>/prototype/prototype-plan.md`

Inspect the repo for:

- `README.md`
- `package.json`
- `tailwind.config.*`
- `app/`
- `pages/`
- `src/`
- `components/`
- `styles/`
- `theme/`
- `tokens/`
- `public/`
- `design/`

For React, Next.js, or Tailwind apps, also look for:

- `tailwind.config.ts`
- `globals.css`
- `components/ui/`
- `components/`
- `app/layout.tsx`
- `app/page.tsx`
- `src/components/`

Adapt the inspection pass for other stacks.

## Design System Modes

Classify the request before producing artifacts:

- `new-design-system`: create foundations and reusable standards from product/UX context.
- `audit-existing-design-system`: document current tokens, components, conventions, gaps, and drift.
- `prototype-design-system`: define a lightweight visual system for a prototype or MVP.
- `production-design-system`: define stricter foundations, governance, accessibility, implementation, and review expectations.
- `component-library-plan`: focus on component inventory, variants, states, props, and usage rules.
- `implementation-scaffold`: optionally scaffold tokens or components only when the user explicitly asks for source changes.

## Workflow

1. Classify the design-system mode.
2. Inspect upstream product/UX artifacts and existing UI conventions before defining visual or component rules.
3. Define the design-system scope, target product surface, users, constraints, and non-goals.
4. Define design principles and foundations: colour, typography, spacing, layout, radius, shadow, borders, icons, motion, and breakpoints.
5. Define design tokens using implementation-friendly names and stable categories.
6. Create a component inventory with purpose, variants, states, accessibility requirements, and usage rules.
7. Define state coverage for loading, empty, error, success, disabled, focus, hover, active, selected, and permission states where relevant.
8. Map the design system to implementation: CSS variables, Tailwind theme, component props, existing UI library, Storybook, Figma tokens, or other repo conventions.
9. Identify gaps, risks, and open questions.
10. Recommend the next lifecycle skill, usually `build-ui-prototype` or `implement-feature-safely`.

## Scope

Before writing artifacts, define:

- Product surface: MVP prototype, internal dashboard, SaaS product, marketing website, admin portal, customer-facing app, or multi-product platform.
- Design-system mode.
- In-scope foundations and components.
- Out-of-scope surfaces, brand work, components, or implementation.
- Whether source changes are requested. Default to planning and documentation only.

## Outputs

Recommended artifact paths:

- `.project/.engineering/initiatives/<initiative-id>/design-system/design-system-plan.md`
- `.project/.engineering/initiatives/<initiative-id>/design-system/design-tokens.md`
- `.project/.engineering/initiatives/<initiative-id>/design-system/component-inventory.md`
- `.project/.engineering/initiatives/<initiative-id>/design-system/accessibility-rules.md`
- `.project/.engineering/initiatives/<initiative-id>/design-system/implementation-mapping.md`

Optional code outputs only when explicitly requested:

- `src/design-system/tokens.ts`
- `src/design-system/components/`
- `src/components/ui/`
- Tailwind config updates
- Storybook stories

Use the files in `templates/` for generated design-system artifacts.

## Required Front Matter

Generated Markdown artifacts must include:

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

## Required Sections

The main design-system plan must include:

- Design System Scope
- Product Context
- Design Principles
- Foundations
- Design Tokens
- Component Inventory
- Component States
- Accessibility Rules
- Responsive Rules
- Implementation Mapping
- Open Questions
- Recommended Next Skill

## References

- Read `engineering-lifecycle/references/design-system-scope-guide.md` when choosing scope, mode, lifecycle position, and output boundaries.
- Read `engineering-lifecycle/references/component-state-guide.md` when defining component variants, states, behaviours, and anti-patterns.
- Read `engineering-lifecycle/references/accessibility-checklist.md` when defining accessibility rules and checks.
- Use `examples/` for realistic invocation patterns and expected output shape.

## Lifecycle Position

Use this skill between UX planning and UI implementation:

```text
create-prd
-> create-ux-flow
-> create-design-system
-> build-ui-prototype
-> implement-feature-safely
-> review-change
```

Keep the boundary clear: `create-design-system` plans and documents the design system by default; `build-ui-prototype` uses the design system to build screens; `implement-feature-safely` productionises or deepens implementation.

## Safety Constraints

- Do not invent brand rules, existing components, colours, or design conventions.
- Clearly separate proposed design decisions from inspected existing conventions.
- Do not modify source code unless the user explicitly asks for implementation.
- Do not claim accessibility compliance; provide accessibility rules and checks.
- Prefer simple MVP-ready systems over over-engineered component libraries.
- Keep design tokens implementation-friendly.
- Preserve existing project conventions unless there is a strong reason to change them.

## Final Response

Include:

- Design System Created
- Files Changed
- Scope And Mode
- Artifacts Produced
- Existing vs Proposed Conventions
- Implementation Mapping
- Open Questions
- Recommended Next Skill

## Related Agents

- `ux-flow-designer`
- `frontend-engineer`
- `requirements-analyst`
- `qa-test-strategist`
- `solution-architect` when the component system affects architecture
- `security-reviewer` when UI exposes sensitive data or permissioned states
