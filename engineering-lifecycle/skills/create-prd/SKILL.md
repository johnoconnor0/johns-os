---
name: create-prd
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*)
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

## Workflow

1. Inspect discovery context, product profile, existing docs/issues/designs, and relevant current behavior before defining requirements.
2. Convert product goals into functional requirements, non-functional requirements, permissions, edge cases, and analytics/observability needs.
3. Write acceptance criteria as testable outcomes tied to user-visible behavior or operational constraints.
4. Split must-have scope from later enhancements and record explicit out-of-scope decisions.
5. Capture open questions whose answers would change scope, acceptance criteria, or release risk.
6. Validate the artifact with `python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" .project/.engineering/initiatives/<initiative-id>/requirements/prd.md`.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/requirements/prd.md`

## Required Sections

- Problem
- Goals
- Users
- Functional Requirements
- Non-Functional Requirements
- Permissions And Data Handling
- Acceptance Criteria
- Edge Cases
- Out Of Scope
- Open Questions

## Safety Constraints

- Do not over-specify implementation details unless required by the product constraint.
- Separate must-have requirements from later enhancements.
- Keep acceptance criteria measurable.

## Related Agents

- `requirements-analyst`
- `product-discovery-lead`
- `qa-test-strategist`
