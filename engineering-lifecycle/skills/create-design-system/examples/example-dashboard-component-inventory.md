---
initiative_id: example-dashboard-components
skill: create-design-system
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# Dashboard Component Inventory Example

## Prompt

```text
Use create-design-system to create a component system for the dashboard.
```

## Expected Handling

- Inspect dashboard UX flows, screen inventory, existing cards/tables/forms/navigation, and styling conventions.
- Classify the mode as `component-library-plan`.
- Prioritize practical MVP dashboard components.
- Define variants, states, props/data inputs, accessibility rules, responsive behaviour, usage examples, and anti-patterns.

## Starter Components

| Component | Purpose | Typical States |
| --- | --- | --- |
| Button | Trigger primary and secondary actions | default, hover, focus, disabled, loading |
| Card | Group dashboard content | default, empty, loading, error |
| Table | Compare rows of operational data | empty, loading, error, selected |
| MetricCard | Highlight KPI values | loading, stale, warning, success |
| EmptyState | Explain missing data and next action | default |
| Alert | Show status, warning, or error feedback | info, success, warning, error |
