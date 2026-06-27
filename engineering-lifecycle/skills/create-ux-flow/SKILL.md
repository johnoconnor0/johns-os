---
name: create-ux-flow
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

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/ux/ux-flow.md`
- `.project/.engineering/initiatives/<initiative-id>/ux/screen-inventory.md`

## Safety Constraints

- Do not claim visual parity with a design unless inspected.
- Keep accessibility and state coverage explicit.
- Do not implement UI during flow planning.

## Related Agents

- `ux-flow-designer`
- `frontend-engineer`
- `requirements-analyst`
