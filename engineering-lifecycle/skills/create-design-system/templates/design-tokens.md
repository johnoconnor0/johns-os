---
initiative_id: example-initiative
skill: create-design-system
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - design-system-plan.md
---

# Design Tokens

## Token Naming Rules

- Use semantic names where possible.
- Avoid raw colour names in component code unless they are palette primitives.
- Separate primitive tokens from semantic tokens.
- Keep token names stable enough for implementation.

## Colour Tokens

### Primitive Tokens

| Token | Value | Usage |
| --- | --- | --- |
| color.blue.500 | #000000 | Brand primitive |

### Semantic Tokens

| Token | Value / Reference | Usage |
| --- | --- | --- |
| color.background.default | reference | Main page background |
| color.text.primary | reference | Main text |
| color.action.primary | reference | Primary action |

## Typography Tokens

| Token | Value | Usage |
| --- | --- | --- |
| font.size.sm | value | Small text |
| font.size.base | value | Body text |
| font.weight.semibold | value | Emphasis |

## Spacing Tokens

| Token | Value | Usage |
| --- | --- | --- |
| space.1 | value | Tight spacing |
| space.4 | value | Default component gap |

## Radius Tokens

| Token | Value | Usage |
| --- | --- | --- |
| radius.sm | value | Small controls |
| radius.md | value | Cards/buttons |

## Shadow Tokens

| Token | Value | Usage |
| --- | --- | --- |
| shadow.card | value | Cards |

## Component Tokens

| Component | Token | Usage |
| --- | --- | --- |
| Button | button.height.md | Medium button height |
