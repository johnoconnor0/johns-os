---
name: create-design-system
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*)
description: Use when the user asks to plan, document, create, audit, or implement a design system, UI kit, component system, design tokens, typography, colours, spacing, accessibility rules, or reusable frontend component standards. Works for any stack, not only React - PHP, WordPress, Laravel, Vue and static HTML have their own adapters.
argument-hint: "[--adapter=<react-tailwind|react-css|vue-nuxt|php-native|wordpress|laravel-blade|static-html>]"
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
- Use `create-technical-design-document` when the user wants broad architecture planning.
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
- `.project/docs/engineering/<initiative-id>/discovery-brief.md`
- `.project/docs/engineering/<initiative-id>/prd.md`
- `.project/docs/engineering/<initiative-id>/app-flow.md`
- `.project/docs/engineering/<initiative-id>/screen-inventory.md`
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

Then inspect the files that matter for the detected stack:

| Stack | Look for |
| --- | --- |
| React / Next / Tailwind | `tailwind.config.*`, `globals.css`, `app/layout.tsx`, `src/components/ui/` |
| Vue / Nuxt | `nuxt.config.*`, `assets/css/`, `components/ui/` |
| PHP | `composer.json`, `templates/`, `assets/css/`, `includes/` |
| WordPress | `theme.json`, `style.css`, `patterns/`, `parts/`, `functions.php` |
| Laravel | `resources/views/components/`, `resources/css/`, `tailwind.config.js` |
| Static HTML | `css/`, `index.html`, any partial or include directory |

## Design System Modes

Classify the request before producing artifacts:

- `new-design-system`: create foundations and reusable standards from product/UX context.
- `audit-existing-design-system`: document current tokens, components, conventions, gaps, and drift.
- `prototype-design-system`: define a lightweight visual system for a prototype or MVP.
- `production-design-system`: define stricter foundations, governance, accessibility, implementation, and review expectations.
- `component-library-plan`: focus on component inventory, variants, states, props, and usage rules.
- `implementation-scaffold`: optionally scaffold tokens or components only when the user explicitly asks for source changes.

## Choose The Adapter

A design system is a set of decisions plus an implementation of those decisions in
one stack. The decisions are portable; the implementation is not. Everything up to
step 7 below is stack-neutral. Step 8 is where the adapter applies.

Read `context/stack.json` (populated with evidence by `detect-stack.py`) and pick:

| Detected | Adapter | Tokens land in | Components land in |
| --- | --- | --- | --- |
| React + Tailwind | `react-tailwind` | `src/design-system/tokens.ts` + `@theme` | `src/components/ui/` |
| React, no Tailwind | `react-css` | `src/design-system/tokens.css` | CSS Modules |
| Vue / Nuxt | `vue-nuxt` | `assets/css/tokens.css` | `components/ui/` |
| PHP, no framework | `php-native` | `assets/css/tokens.css` | `templates/components/*.php` |
| WordPress | `wordpress` | `theme.json` | `patterns/`, `parts/` |
| Laravel | `laravel-blade` | `resources/css/tokens.css` | `resources/views/components/*.blade.php` |
| Static HTML | `static-html` | `css/tokens.css` | HTML partials + class contract |

`--adapter=<name>` overrides detection. Use it when detection is wrong, or when
the target stack does not exist yet. **State which adapter you chose and the
evidence for it.** If the stack is genuinely unclear, ask rather than assuming React.

Read `references/design-system-adapters.md` for each adapter's conventions and the
shared token contract. CSS custom properties are the lowest common denominator and
every adapter emits them, so a component can be ported by changing the wrapper
rather than the values.

## Workflow

1. Classify the design-system mode and choose the adapter.
2. Inspect upstream product/UX artifacts and existing UI conventions before defining visual or component rules.
3. Define the design-system scope, target product surface, users, constraints, and non-goals.
4. Define design principles and foundations: colour, typography, spacing, layout, radius, shadow, borders, icons, motion, and breakpoints.
5. Define design tokens using implementation-friendly names and stable categories.
6. Create a component inventory with purpose, variants, states, accessibility requirements, and usage rules.
7. Define state coverage for loading, empty, error, success, disabled, focus, hover, active, selected, and permission states where relevant.
8. Map the design system to implementation **through the chosen adapter**. Emit CSS
   custom properties in every case, plus the framework-native layer the adapter
   specifies. Use semantic token names (`--accent`, not `--blue-500`).
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

- `.project/docs/engineering/<initiative-id>/design-system/design-system-plan.md`
- `.project/docs/engineering/<initiative-id>/design-system/design-tokens.md`
- `.project/docs/engineering/<initiative-id>/design-system/component-inventory.md`
- `.project/docs/engineering/<initiative-id>/design-system/accessibility-rules.md`
- `.project/docs/engineering/<initiative-id>/design-system/implementation-mapping.md`

Optional code outputs only when explicitly requested. The paths come from the
chosen adapter, not from a React default. See the adapter table above and
`references/design-system-adapters.md`.

Use the files in `templates/` for generated design-system artifacts. The
`implementation-mapping.md` artifact records which adapter was chosen, on what
evidence, and where each token and component category lands in this repo.

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

- Read `engineering-lifecycle/references/design-system-adapters.md` when choosing the adapter and mapping tokens and components into the target stack.
- Read `engineering-lifecycle/references/design-system-scope-guide.md` when choosing scope, mode, lifecycle position, and output boundaries.
- Read `engineering-lifecycle/references/anti-slop-register.md` before proposing any concrete visual direction.
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
