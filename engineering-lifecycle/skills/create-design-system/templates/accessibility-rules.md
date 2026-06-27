---
initiative_id: example-initiative
skill: create-design-system
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - design-system-plan.md
---

# Accessibility Rules

## Keyboard

- All interactive elements must be reachable by keyboard.
- Focus order must follow visual order.
- Custom controls must preserve keyboard semantics.

## Focus

- Focus state must be visible.
- Focus should not be trapped unless inside modal/dialog patterns.
- Modals must return focus to the trigger when closed.

## Text And Labels

- Form fields require visible labels or accessible names.
- Buttons and links must have descriptive text.
- Icon-only controls require accessible labels.

## Colour And Contrast

- Colour must not be the only way to communicate status.
- Error/success states must include text or icon support.
- Proposed colour combinations require contrast checking before production.

## Errors

- Error messages must identify the issue and recovery action.
- Form errors should be linked to fields where possible.

## Motion

- Avoid unnecessary motion.
- Respect reduced-motion preferences where possible.

## Component-Specific Notes

| Component | Accessibility Requirement |
| --- | --- |
| Button | Visible focus, disabled/loading semantics |
| Modal | Focus management, escape close, labelled title |
| FormField | Label, error text, hint text association |
