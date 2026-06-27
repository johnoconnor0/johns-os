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

## Outputs

- `.project/.engineering/lifecycle/lifecycle-map.md`
- `.project/.engineering/lifecycle/lifecycle-state.yaml`
- `.project/.engineering/lifecycle/missing-artifacts.json`

## Safety Constraints

- Treat missing artifacts as planning gaps, not failures.
- Distinguish confirmed evidence from inferred lifecycle state.
- Do not create downstream artifacts unless requested.

## Related Agents

- `product-discovery-lead`
- `solution-architect`
- `qa-test-strategist`
