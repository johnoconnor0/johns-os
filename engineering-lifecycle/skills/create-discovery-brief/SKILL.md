---
name: create-discovery-brief
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*)
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

## Workflow

1. Inspect the user prompt, product profile, README, existing docs, issues, and any stakeholder notes before writing product claims.
2. Separate confirmed facts from assumptions and mark unknowns that materially affect the MVP boundary.
3. Define the problem, affected users, current workaround, desired outcome, success signals, constraints, risks, and explicit non-goals.
4. Convert unclear product or business facts into open questions rather than inventing answers.
5. Recommend the next lifecycle artifact, usually `create-prd`, only when discovery is specific enough for requirements.
6. Validate the artifact with `python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" .project/docs/engineering/<initiative-id>/discovery-brief.md`.

## Outputs

- `.project/docs/engineering/<initiative-id>/discovery-brief.md`

## Required Sections

- Problem
- Users
- Evidence
- Goals And Success Signals
- Assumptions
- Risks
- MVP Boundary
- Open Questions
- Recommended Next Artifact

## Safety Constraints

- Do not invent business facts.
- Mark assumptions separately from confirmed context.
- Keep MVP boundaries explicit.

## Related Agents

- `product-discovery-lead`
- `requirements-analyst`
