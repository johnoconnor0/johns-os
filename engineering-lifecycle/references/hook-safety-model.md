# Hook Safety Model

Hooks are guardrails and context emitters. They should not become broad editing agents.

## SessionStart

Session start hooks may report project context and workspace availability. They must stay fast and avoid source edits.

## PreToolUse

Pre-tool hooks may block explicit unsafe commands such as destructive git resets, broad recursive deletes, or likely secret exfiltration. Blocks must be narrow and explain why the command was stopped.

## PostToolUse

Post-tool hooks may detect hygiene drift, validate generated artifacts, and sync ledgers. They should write reports or structured context rather than silently editing source files.

## Stop

Stop hooks may remind the assistant about hygiene drift, missing generated artifacts, or incomplete completion contracts. They should block only when a deterministic safety or validity condition fails.

## Exit Codes

- `0`: report, suggestion, or successful validation.
- nonzero: explicit safety block or invalid generated artifact.
