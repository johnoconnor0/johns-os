---
name: create-discovery-brief
description: Use to turn a product idea, problem, or vague initiative into a clear discovery brief with users, goals, risks, assumptions, and MVP boundary.
---

# Create Discovery Brief

## Trigger

Use when the user has an idea, product problem, feature concept, or business goal that needs clarification before requirements or design.

## When To Use

- Before writing a PRD.
- When the user has not yet defined the target user or success criteria.
- When assumptions and open questions need to be made explicit.

## Inputs Inspected

- User prompt and stakeholder notes.
- Product profile.
- Existing docs, customer notes, or issue descriptions.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/discovery/discovery-brief.md`

## Safety Constraints

- Do not invent business facts.
- Mark assumptions separately from confirmed context.
- Keep MVP boundaries explicit.

## Related Agents

- `product-discovery-lead`
- `requirements-analyst`
