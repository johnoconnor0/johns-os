# Recommended Prompts And Evals

## Example Prompts

```text
Use build-ui-prototype to create a clickable dashboard prototype from the existing PRD and UX flow. Use mock data only.
```

```text
Use build-ui-prototype to build the first MVP UI slice for onboarding: welcome screen, connect account screen, loading state, and success screen.
```

```text
Use build-ui-prototype to create a SaaS app shell with sidebar navigation, dashboard cards, empty state, and placeholder report table.
```

```text
Use build-ui-prototype to prototype the audit report screen using mock data. Do not connect the real API yet.
```

```text
Use build-ui-prototype to build a demo-ready UI for the current feature branch, then document what is mocked and what remains production work.
```

## Trigger Evals

```json
[
  {
    "prompt": "Build a clickable MVP dashboard using mock data",
    "should_trigger": "build-ui-prototype"
  },
  {
    "prompt": "Create a UI prototype for this onboarding flow",
    "should_trigger": "build-ui-prototype"
  },
  {
    "prompt": "Map the screens and empty states but do not implement",
    "should_trigger": "create-ux-flow"
  },
  {
    "prompt": "Implement the backend API for this feature",
    "should_trigger": "implement-feature-safely"
  },
  {
    "prompt": "Review the prototype branch for UI state coverage",
    "should_trigger": "review-change"
  }
]
```

## Output Evals

Check that `build-ui-prototype` outputs:

- Prototype mode.
- Screens included.
- Screens excluded.
- Mock vs real behaviour.
- Planned files.
- Validation commands.
- Limitations.
- QA checklist.
- Follow-up tasks.
