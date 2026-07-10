---
name: create-architecture-plan
description: Use to turn product and system understanding into an implementable architecture plan, module boundaries, tradeoffs, and ADR candidates.
---

# Create Architecture Plan

## Trigger

Use when the user asks for architecture, technical direction, module boundaries, design tradeoffs, scaling shape, or ADRs.

## When To Use

- After system mapping.
- Before data/API design and implementation planning.
- When a technical decision has meaningful tradeoffs.

## Inputs Inspected

- System map, PRD, UX flow, and product profile.
- Current architecture, package boundaries, deployment model, and constraints.
- Relevant prior decisions under `.project/.engineering/decisions`.

## Workflow

1. Inspect upstream artifacts and current code boundaries before recommending architecture.
2. List constraints, non-goals, operational assumptions, and decisions already made.
3. Define the recommended architecture, module ownership, interfaces, migration impact, and rollout/rollback considerations.
4. Record alternatives considered and why they were rejected.
5. Create ADR candidates for decisions that affect durable architecture or operations.
6. Convene `run-engineering-council` for high-stakes, irreversible, or cross-cutting decisions before finalizing (the prompt intake also flags these and suggests it).
7. Run `python scripts/validate-artifact.py .project/.engineering/initiatives/<initiative-id>/architecture/architecture-plan.md`.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/architecture/architecture-plan.md`
- `.project/.engineering/decisions/ADR-<number>-<slug>.md`

## Required Front Matter

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

## Required Sections

- Decision Summary
- Constraints
- Recommended Architecture
- Interfaces And Boundaries
- Alternatives Considered
- Risks
- Migration And Rollback
- ADR Candidates

## Safety Constraints

- Distinguish recommended decisions from alternatives considered.
- Do not invent operational constraints.
- Reserve council review for high-stakes, irreversible, or cross-cutting decisions; skip it for routine ones.

## Related Agents

- `solution-architect`
- `security-reviewer`
- `database-engineer`
- `devops-release-engineer`
