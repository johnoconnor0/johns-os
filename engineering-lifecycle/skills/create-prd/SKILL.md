---
name: create-prd
description: Use to produce a practical product requirements document with functional requirements, non-functional requirements, user stories, and acceptance criteria.
---

# Create PRD

## Trigger

Use when the user asks for requirements, acceptance criteria, user stories, product scope, or a feature spec.

## When To Use

- After discovery is clear enough to define behavior.
- Before UX, system mapping, architecture, or implementation planning.
- When scope needs to be testable.

## Inputs Inspected

- Discovery brief.
- Product profile.
- Existing issues, docs, designs, and user prompt.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/requirements/prd.md`

## Safety Constraints

- Do not over-specify implementation details unless required by the product constraint.
- Separate must-have requirements from later enhancements.
- Keep acceptance criteria measurable.

## Related Agents

- `requirements-analyst`
- `product-discovery-lead`
- `qa-test-strategist`
