---
name: profile-product-system
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*)
description: Use at the start of product or repo work to understand the product, users, stack, integrations, constraints, and development maturity.
---

# Profile Product System

## Trigger

Use when the user asks to understand a product, repo, stack, project context, integration surface, or current engineering maturity before planning work.

## When To Use

- Starting a new initiative.
- Joining an unfamiliar codebase.
- Creating baseline product, repo, and tech-stack context.
- Preparing inputs for lifecycle mapping or architecture work.

## Inputs Inspected

- User-provided product context.
- README and project docs.
- Repo structure and package manifests.
- Configuration examples and deployment hints.
- Existing generated artifacts under `.project/.engineering`.

## Workflow

1. Run or emulate `python "${CLAUDE_PLUGIN_ROOT}/scripts/profile-repo.py" --print` to collect factual repo shape.
2. Inspect README, docs, package manifests, deployment config, and existing `.project/.engineering/profile` artifacts.
3. Separate confirmed facts from product assumptions. Mark unknown users, workflows, integrations, constraints, and ownership explicitly.
4. Write the three profile outputs using the template fields and stable YAML keys.
5. Emit action items for missing critical facts such as unknown deploy target, owner, secrets policy, or primary user.
6. Validate generated Markdown/JSON with `python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" <artifact paths>`.

## Outputs

- `.project/.engineering/profile/product-system-profile.yaml`
- `.project/.engineering/profile/tech-stack-profile.yaml`
- `.project/.engineering/profile/repo-profile.yaml`

## Required Front Matter

Generated Markdown companion artifacts must include:

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

YAML/JSON profile files must include equivalent top-level metadata where practical.

## Uncertainty Handling

- Use `unknown` rather than guessing.
- Include an `unknowns` list with why each item matters.
- Cite files inspected for every non-obvious repo or product claim.

## Action Items

Record open questions as checklist items or `action_items` JSON entries so `scripts/emit-action-items.py` and `scripts/sync-ledger.py` can ingest them.

## Safety Constraints

- Do not infer secrets from local config values.
- Mark unknowns explicitly instead of guessing.
- Do not edit source files during profiling.

## Related Agents

- `product-discovery-lead`
- `solution-architect`
- `repo-hygiene-maintainer`
