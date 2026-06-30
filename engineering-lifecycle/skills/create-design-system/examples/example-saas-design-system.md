---
initiative_id: example-saas-design-system
skill: create-design-system
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# SaaS Design System Example

## Prompt

```text
Use create-design-system to plan a simple MVP design system for this SaaS dashboard before we build the prototype.
```

## Expected Handling

- Inspect product profile, PRD, UX flow, screen inventory, current UI files, styling conventions, and package scripts.
- Classify the mode as `prototype-design-system` or `new-design-system`.
- Define design principles, foundations, tokens, components, state coverage, accessibility rules, and implementation mapping.
- Keep the system MVP-ready and avoid broad brand work unless provided.
- Recommend `build-ui-prototype` as the next skill when the design system is ready for screens.

## Expected Outputs

- `design-system-plan.md`
- `design-tokens.md`
- `component-inventory.md`
- `accessibility-rules.md`
- `implementation-mapping.md`
