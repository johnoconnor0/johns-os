# Engineering Council Design

The engineering council is an optional high-stakes decision workflow. It is not the default planning path.

Use it for:

- major architecture choices,
- build-vs-buy decisions,
- risky migrations,
- security-sensitive designs,
- scaling and AI-system tradeoffs.

Do not use it for routine bug fixes, simple docs changes, or decisions where a normal implementation plan is sufficient.

## Roles

- Contrarian: challenges assumptions and downside risk.
- First-Principles Thinker: reduces the decision to constraints and invariants.
- Expansionist: looks for optionality and broader opportunity.
- Outsider: applies external perspective.
- Executor: focuses on implementation cost and delivery risk.
- Chairperson: synthesizes, preserves dissent, and records next actions.

## Runtime Shape

Council runs write:

- `input.json`
- `advisor-drafts/`
- `anonymized-drafts/`
- `peer-reviews/`
- `synthesis.md`
- `events.jsonl`

The local implementation is deterministic and fixture-friendly. Live model orchestration uses the same artifact boundary and is explicitly opt-in.

## Live Adapters

Supported adapter modes:

- `command`: runs `ENGINEERING_COUNCIL_ADAPTER_COMMAND`, sends JSON on stdin, and accepts Markdown or JSON content on stdout.
- `anthropic`: calls Anthropic Messages API using `ANTHROPIC_API_KEY` and `ENGINEERING_COUNCIL_MODEL`.
- `openai`: calls OpenAI-compatible chat completions using `OPENAI_API_KEY` and `ENGINEERING_COUNCIL_MODEL`.

Live mode should be used only when the supplied context is safe to send to the configured model or command. Use deterministic mode for private, offline, fixture, or CI workflows.

## Quorum

Minimum quorum is three advisor drafts. If quorum fails, produce artifacts with `quorum-failed` status and do not present the recommendation as final.
