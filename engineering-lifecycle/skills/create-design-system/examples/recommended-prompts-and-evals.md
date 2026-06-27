# Recommended Prompts And Evals

## Example Prompts

```text
Use create-design-system to plan a simple MVP design system for this SaaS dashboard before we build the prototype.
```

```text
Use create-design-system to inspect the existing frontend and document the current design tokens, components, and inconsistencies.
```

```text
Use create-design-system to create a design system for a Google Ads audit dashboard with cards, tables, forms, alerts, and report screens.
```

```text
Use create-design-system to define colours, typography, spacing, buttons, inputs, cards, tables, empty states, and accessibility rules for the MVP.
```

```text
Use create-design-system to create implementation-ready component specs that can be handed to build-ui-prototype.
```

## Trigger Evals

```json
[
  {
    "prompt": "Create a design system for this SaaS MVP before we build the UI prototype",
    "should_trigger": "create-design-system"
  },
  {
    "prompt": "Define colours, typography, spacing, and reusable components for the dashboard",
    "should_trigger": "create-design-system"
  },
  {
    "prompt": "Audit the current app and document its UI tokens and component inconsistencies",
    "should_trigger": "create-design-system"
  },
  {
    "prompt": "Map the user journeys and screen states",
    "should_trigger": "create-ux-flow"
  },
  {
    "prompt": "Build a clickable prototype using the design system",
    "should_trigger": "build-ui-prototype"
  }
]
```
