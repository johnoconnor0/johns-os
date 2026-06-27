---
initiative_id: example-initiative
skill: create-design-system
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - design-system-plan.md
  - design-tokens.md
  - component-inventory.md
---

# Design System Implementation Mapping

## Current Stack

- Framework:
- Styling:
- Component library:
- Existing component path:
- Existing token/theme path:

## Recommended File Structure

```text
src/
  components/
    ui/
  design-system/
    tokens.ts
    components.md
  styles/
```

## Token Mapping

| Token Category | Implementation Location | Notes |
| --- | --- | --- |
| Colour | Tailwind config / CSS variables | Notes |
| Spacing | Tailwind spacing scale | Notes |
| Typography | CSS/Tailwind theme | Notes |

## Component Mapping

| Component | Implementation Path | Source / Dependency | Notes |
| --- | --- | --- | --- |
| Button | components/ui/button.tsx | existing/new | Notes |

## Prototype Usage

- Components needed for `build-ui-prototype`:
- Mock-data considerations:
- Layout considerations:

## Productionisation Notes

- Tests required:
- Accessibility checks:
- Storybook/docs:
- Review gates:

## Open Questions

- [ ] Question:
