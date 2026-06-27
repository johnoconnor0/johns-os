---
initiative_id: example-initiative
skill: create-design-system
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - ../requirements/prd.md
  - ../ux/ux-flow.md
  - ../ux/screen-inventory.md
---

# Design System Plan

## Design System Scope

- Product surface:
- Target users:
- Primary use case:
- Design-system mode:
- In scope:
- Out of scope:

## Product Context

- Product goal:
- UX flows supported:
- Screens supported:
- Constraints:

## Design Principles

1. Principle:
   - Meaning:
   - Implementation implication:

## Foundations

### Colour

- Brand colours:
- Neutral colours:
- Semantic colours:
- Data/status colours:

### Typography

- Font family:
- Type scale:
- Heading rules:
- Body text rules:
- Label/caption rules:

### Spacing

- Spacing scale:
- Page padding:
- Component gap rules:

### Layout

- Page layout:
- Grid:
- Container width:
- Sidebar/nav rules:
- Responsive behaviour:

### Radius, Border, Shadow

- Radius scale:
- Border rules:
- Elevation/shadow rules:

### Motion

- Transition rules:
- Motion limits:
- Reduced-motion behaviour:

## Design Tokens

- Token naming approach:
- Primitive tokens:
- Semantic tokens:
- Component tokens:

## Component Inventory

| Component | Purpose | Priority | Variants | States |
| --- | --- | --- | --- | --- |
| Button | Primary user actions | Must | primary, secondary, ghost | default, hover, focus, disabled, loading |

## Component States

| State | Required Behaviour | Applies To |
| --- | --- | --- |
| Loading | Show progress without layout shift | buttons, pages, cards, tables |

## Accessibility Rules

- Keyboard:
- Focus:
- Labels:
- Colour contrast:
- Screen reader:
- Motion:
- Error messaging:

## Responsive Rules

| Breakpoint | Layout Behaviour | Notes |
| --- | --- | --- |
| Mobile | Single-column layout | Preserve primary actions |

## Implementation Mapping

| Design System Area | Implementation Target | Notes |
| --- | --- | --- |
| Colours | Tailwind theme / CSS variables | Use token names, not raw values in components |

## Risks

- Risk:
- Mitigation:

## Open Questions

- [ ] Question:

## Recommended Next Skill

- Suggested skill:
- Reason:
