---
name: create-system-map
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*)
description: Use to map actors, workflows, components, data flow, external systems, responsibility boundaries, failure points, security, and deployment shape.
---

# Create System Map

## Trigger

Use when the user asks to understand architecture, map a system, identify components, external systems, workflows, data flow, or failure points.

## When To Use

- Before architecture planning.
- When codebase boundaries are unclear.
- When onboarding to an existing system.
- Before risky implementation or migration work.

## Inputs Inspected

- Repo structure and runtime entrypoints.
- Product profile, PRD, and UX flow.
- Config files, deployment notes, schema files, API routes, and integration points.

## Workflow

1. Inspect repo entrypoints, routing, service boundaries, schema/data files, auth/config, deployment files, and existing lifecycle artifacts.
2. Identify actors, external systems, major workflows, components, data entities, data flow, failure points, security boundaries, and deployment shape.
3. Mark each claim as confirmed from inspected evidence or inference.
4. Produce `system-map.md`, `context-diagram.mmd`, and `container-diagram.mmd`.
5. Emit action items for missing diagrams, unknown owners, unclear security boundaries, or undocumented external dependencies.
6. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" .project/.engineering/initiatives/<initiative-id>/system-map/system-map.md`.

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/system-map/system-map.md`
- `.project/.engineering/initiatives/<initiative-id>/system-map/context-diagram.mmd`
- `.project/.engineering/initiatives/<initiative-id>/system-map/container-diagram.mmd`

## Required Front Matter

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

## Required Sections

- Product Context
- Actors And External Systems
- Workflows
- Components
- Data Flow
- Security And Permissions
- Deployment
- Failure Modes
- Missing Information
- Recommended Next Artifacts

## Safety Constraints

- Ground component claims in inspected files or clearly mark inference.
- Do not edit source files.
- Record missing information instead of filling gaps with guesses.

## Related Agents

- `solution-architect`
- `domain-modeller`
- `security-reviewer`
- `devops-release-engineer`
