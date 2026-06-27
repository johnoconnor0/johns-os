# Design System Scope Guide

Use this guide to keep design-system work practical, implementation-ready, and correctly bounded.

## Mode Selection

| Mode | Use When | Output Bias |
| --- | --- | --- |
| `new-design-system` | Product/UX context exists but no reusable design system is documented | Foundations, tokens, component inventory, implementation mapping |
| `audit-existing-design-system` | The repo already has UI conventions, components, or token files | Existing conventions, inconsistencies, gaps, risks |
| `prototype-design-system` | A quick MVP or clickable prototype needs visual consistency | Minimal foundations, essential components, state rules |
| `production-design-system` | The system will support durable implementation and review | Governance, accessibility checks, token stability, component specs |
| `component-library-plan` | Components are the primary output | Inventory, variants, states, props, accessibility, examples |
| `implementation-scaffold` | The user explicitly asks to scaffold code | Minimal source changes mapped to existing framework conventions |

## Scope Questions

- Is the design system for an MVP prototype, internal dashboard, SaaS product, marketing website, admin portal, customer-facing app, or multi-product platform?
- Which user journeys and screens must it support first?
- Which existing UI conventions are confirmed by inspected files?
- Which rules are proposed because no current convention exists?
- Is code implementation explicitly requested?

## Boundary Rules

- Default to planning and documentation.
- Do not modify source code unless implementation is explicitly requested.
- Do not invent brand rules, colour palettes, fonts, logos, or component conventions.
- Prefer a small MVP-ready system over a broad generic library.
- Separate inspected existing conventions from proposed recommendations.
- Connect every major foundation or component rule to implementation guidance.

## Minimum Useful MVP System

- 3 to 5 design principles.
- Colour, typography, spacing, layout, radius, border, shadow, motion, and breakpoint foundations.
- Semantic design tokens.
- Component inventory for core workflows.
- State coverage rules.
- Accessibility rules.
- Implementation mapping to the current stack.
