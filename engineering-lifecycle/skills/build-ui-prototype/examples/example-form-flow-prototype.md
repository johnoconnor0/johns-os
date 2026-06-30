---
initiative_id: example-onboarding-flow
skill: build-ui-prototype
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# Form Flow Prototype Example

## Prompt

```text
Use build-ui-prototype to build the first MVP UI slice for onboarding: welcome screen, connect account screen, loading state, and success screen.
```

## Expected Handling

- Inspect existing form, route, validation, component, and styling conventions.
- Classify the mode as clickable prototype or vertical MVP slice.
- Use local state and mock transitions unless existing APIs are defined and approved.
- Include labels, visible focus states, form validation feedback, loading, error, and success states.
- Document mocked account connection behaviour and production integration requirements.

## Useful Screens

| Screen | Purpose | States |
| --- | --- | --- |
| Welcome | Introduce onboarding path | Default |
| Connect account | Capture intent and simulate account connection | Empty, validation error, loading |
| Success | Confirm completed demo flow | Success |
