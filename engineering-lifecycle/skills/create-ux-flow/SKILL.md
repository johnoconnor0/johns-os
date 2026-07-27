---
name: create-ux-flow
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*)
description: Use to map user journeys, screens, states, interaction flows, accessibility considerations, and screen inventory for a product or feature.
---

# Create UX Flow

## Trigger

Use when the user asks for user journeys, screen flow, UI states, interaction design, or a screen inventory.

## When To Use

- After requirements are known.
- Before frontend architecture or implementation planning.
- When empty, loading, error, permission, or accessibility states need coverage.

## Inputs Inspected

- PRD and discovery brief.
- Existing UI files and design conventions.
- Product profile and user types.

## Workflow

1. Inspect the PRD, discovery brief, existing UI routes/components, and design conventions before defining screens or states.
2. Identify primary users, entry points, happy paths, alternate paths, and exit points.
3. Define screen inventory, state matrix, key interactions, empty/loading/error/success/permission states, and accessibility considerations.
4. Mark any visual, content, or design-system claim as confirmed only when inspected.
5. Record unresolved UX decisions as open questions with the downstream implementation impact.
6. Validate generated UX artifacts with `python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" <artifact paths>`.

## Outputs

- `.project/docs/engineering/<initiative-id>/app-flow.md`
- `.project/docs/engineering/<initiative-id>/screen-inventory.md`

## Required Sections

- Users
- Journeys
- Screens
- States
- Edge Cases
- Accessibility
- Open Questions

## Safety Constraints

- Do not claim visual parity with a design unless inspected.
- Keep accessibility and state coverage explicit.
- Do not implement UI during flow planning.

## Related Agents

- `ux-flow-designer`
- `frontend-engineer`
- `requirements-analyst`
