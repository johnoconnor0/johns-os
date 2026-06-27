# UI State Coverage Guide

Use this guide to decide which states a prototype should represent without overbuilding.

## Required State Pass

For each included screen or component, consider:

| State | Include When | Prototype Approach |
| --- | --- | --- |
| Empty | Lists, dashboards, search, setup, or reports can have no data | Add a clear empty state with next action |
| Loading | User action or route implies waiting | Use local state, skeleton, spinner, or disabled control |
| Error | Data, validation, or action can fail | Add visible error copy and recovery action |
| Success | A journey has a completion point | Add confirmation, status, or next step |
| Permission | Auth, role, account, or restricted data is shown | Add an unauthorised or unavailable state only if relevant |

## Accessibility Baseline

- Use semantic headings, buttons, links, labels, and table structures where appropriate.
- Ensure primary actions are keyboard reachable.
- Use visible focus styles from the existing design system.
- Do not use colour as the only signal for status.
- Keep button and link text clear.
- Use accessible names for icon-only controls.

## Responsive Baseline

- Verify the primary journey at mobile and desktop widths when possible.
- Avoid fixed-width layouts that overflow common mobile widths.
- Keep navigation usable when horizontal space is limited.
- Preserve readable table or card alternatives for narrow screens.

## Validation Notes

- Prefer automated lint, typecheck, tests, or build commands when available.
- Add lightweight tests only when they fit the repo's existing test setup and the prototype behaviour has meaningful logic.
- If automated checks are unavailable, document manual QA steps and state that no automated validation was available.
