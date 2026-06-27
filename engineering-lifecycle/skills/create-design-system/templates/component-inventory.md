---
initiative_id: example-initiative
skill: create-design-system
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - design-system-plan.md
---

# Component Inventory

## Summary

- Components required for MVP:
- Components required later:
- Existing components reused:
- Components to avoid duplicating:

## Component List

| Component | Priority | Purpose | Existing / New | Notes |
| --- | --- | --- | --- | --- |
| Button | Must | Trigger actions | Existing/New | Notes |

## Component Specs

### Button

#### Purpose

- User-facing job:
- Product contexts:

#### Variants

- Primary
- Secondary
- Ghost
- Destructive

#### States

- Default
- Hover
- Focus
- Active
- Disabled
- Loading

#### Props / Inputs

| Prop | Type | Required | Notes |
| --- | --- | --- | --- |
| variant | enum | no | primary, secondary, ghost |

#### Accessibility

- Must be keyboard accessible.
- Must have visible focus state.
- Loading state must remain understandable.

#### Usage Rules

Use when:

- Rule:

Do not use when:

- Rule:

#### Example

```tsx
<Button variant="primary">Save</Button>
```

## Open Questions

- [ ] Question:
