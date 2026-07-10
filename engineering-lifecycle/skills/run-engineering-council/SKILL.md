---
name: run-engineering-council
description: Convene an independent multi-perspective engineering council before high-stakes or hard-to-reverse work — major architecture, a new plugin or subsystem, external integrations, risky migrations, security-sensitive or AI-system design, or build-vs-buy. Invoke proactively when a change is large, cross-cutting, or costly to undo, not only when explicitly asked; skip it for routine bug fixes and simple docs.
---

# Run Engineering Council

## Trigger

Use proactively before starting an enormous, irreversible, or cross-cutting change, and whenever the user asks for a council review. The user-prompt intake flags high-stakes signals (new plugin/subsystem, architecture, external provider/integration, migration, security, AI-system, build-vs-buy) and suggests this skill — act on that suggestion rather than waiting to be asked.

## When To Use

- Major architecture decisions.
- New plugin, subsystem, or platform-shaping work.
- Build-vs-buy choices.
- Risky or irreversible migrations.
- Security-sensitive or external-integration designs.
- Scaling or AI-system design tradeoffs.

## Inputs Inspected

- Council question.
- Relevant lifecycle artifacts.
- Repo evidence and external constraints supplied by the user.

## Workflow

1. Confirm the question is high-stakes enough for council review.
2. Collect explicit context files or directories; do not broaden scope silently.
3. Run `python scripts/council.py ask --question "<question>" --context <path>` for deterministic local mode.
4. For live model mode, run `python scripts/council.py ask --mode live-model --adapter command|anthropic|openai --question "<question>" --context <path>` after configuring the required environment variables.
5. Preserve independent advisor drafts, anonymized drafts, peer reviews, events, and chair synthesis.
6. Treat deterministic local output as a safe, fixture-friendly baseline; use live adapters only when model cost, credentials, and privacy constraints are acceptable.
7. Validate the synthesis with `python scripts/validate-artifact.py .project/.engineering/council/<run-id>/synthesis.md`.

## Outputs

- `.project/.engineering/council/<run-id>/input.json`
- `.project/.engineering/council/<run-id>/advisor-drafts/`
- `.project/.engineering/council/<run-id>/anonymized-drafts/`
- `.project/.engineering/council/<run-id>/peer-reviews/`
- `.project/.engineering/council/<run-id>/synthesis.md`
- `.project/.engineering/council/<run-id>/events.jsonl`

## Live Adapter Configuration

- `--adapter command` requires `ENGINEERING_COUNCIL_ADAPTER_COMMAND`. The command receives JSON on stdin and returns either plain Markdown or JSON with `content`, `text`, `markdown`, or `response`.
- `--adapter anthropic` requires `ANTHROPIC_API_KEY` and `ENGINEERING_COUNCIL_MODEL`.
- `--adapter openai` requires `OPENAI_API_KEY` and `ENGINEERING_COUNCIL_MODEL`.
- Optional controls: `ENGINEERING_COUNCIL_TIMEOUT_SECONDS`, `ENGINEERING_COUNCIL_MAX_CONTEXT_CHARS`, `ENGINEERING_COUNCIL_MAX_TOKENS`, provider-specific URL overrides, and `--fallback-on-error`.

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
