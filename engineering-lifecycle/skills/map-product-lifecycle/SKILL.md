---
name: map-product-lifecycle
description: Use to identify where a product or initiative sits in the engineering lifecycle and which artifacts are missing.
---

# Map Product Lifecycle

## Trigger

Use when the user asks what should happen next, which planning artifacts are missing, or how mature an initiative is.

## When To Use

- After profiling a product system.
- Before creating PRDs, system maps, implementation plans, or release plans.
- When work feels scattered and needs lifecycle structure.

## Inputs Inspected

- `.project/.engineering/profile/`
- Existing initiative artifacts.
- README, docs, issue notes, and user prompt.
- Repo evidence for implementation, tests, and release maturity.

## Workflow

1. Inspect product profile, initiative directories, README/docs/issues, and repo evidence for implementation, tests, release, and hygiene maturity.
2. Classify each lifecycle stage as missing, draft, reviewed, approved, implemented, or superseded based on artifacts and evidence.
3. Identify missing artifacts, stale artifacts, unresolved blockers, and risks that affect the next lifecycle step.
4. Recommend exactly one primary next skill plus optional follow-up skills when needed.
5. Write lifecycle map, lifecycle state, and missing-artifacts sidecar data when requested.
6. Validate generated artifacts with `python scripts/validate-artifact.py <artifact paths>` and `python scripts/validate-schemas.py`.

## Outputs

- `.project/.engineering/lifecycle/lifecycle-map.md`
- `.project/.engineering/lifecycle/lifecycle-state.yaml`
- `.project/.engineering/lifecycle/missing-artifacts.json`

## Required Sections

- Current Stage
- Artifact Inventory
- Missing Artifacts
- Risks
- Recommended Next Skill
- Action Items

## Safety Constraints

- Treat missing artifacts as planning gaps, not failures.
- Distinguish confirmed evidence from inferred lifecycle state.
- Do not create downstream artifacts unless requested.

## Related Agents

- `product-discovery-lead`
- `solution-architect`
- `qa-test-strategist`
