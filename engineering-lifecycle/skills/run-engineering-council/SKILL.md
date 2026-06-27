---
name: run-engineering-council
description: Use manually for high-stakes engineering decisions that benefit from independent specialist perspectives and synthesized tradeoff analysis.
---

# Run Engineering Council

## Trigger

Use only when the user asks for council review or when a decision is high-stakes enough to justify explicit multi-perspective analysis.

## When To Use

- Major architecture decisions.
- Build-vs-buy choices.
- Risky migrations.
- Security-sensitive designs.
- Scaling or AI-system design tradeoffs.

## Inputs Inspected

- Council question.
- Relevant lifecycle artifacts.
- Repo evidence and external constraints supplied by the user.

## Workflow

1. Confirm the question is high-stakes enough for council review.
2. Collect explicit context files or directories; do not broaden scope silently.
3. Run `python scripts/council.py ask --question "<question>" --context <path>` or create the same artifact structure manually.
4. Preserve independent advisor drafts, peer reviews, events, and chair synthesis.
5. Treat deterministic local output as structured scaffolding until a human or live model adapter replaces placeholder judgment.
6. Validate the synthesis with `python scripts/validate-artifact.py .project/.engineering/council/<run-id>/synthesis.md`.

## Outputs

- `.project/.engineering/council/<run-id>/input.json`
- `.project/.engineering/council/<run-id>/advisor-drafts/`
- `.project/.engineering/council/<run-id>/peer-reviews/`
- `.project/.engineering/council/<run-id>/synthesis.md`
- `.project/.engineering/council/<run-id>/events.jsonl`

## Required Front Matter

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

## Quorum Rules

- Minimum quorum is three advisor drafts.
- If quorum fails, write artifacts anyway with `quorum-failed` status and do not present a recommendation as final.
- Chair synthesis must preserve meaningful dissent.

## Safety Constraints

- Do not use council for routine bug fixes or simple docs changes.
- Keep advisor positions evidence-bound.
- Chair synthesis must preserve meaningful dissent.

## Related Agents

- `council-contrarian`
- `council-first-principles`
- `council-expansionist`
- `council-outsider`
- `council-executor`
- `council-chairperson`
