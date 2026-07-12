#!/usr/bin/env bash
# ai-utilities — plugin welcome hook (SessionStart)

read -r -d '' MESSAGE <<'EOF'
ai-utilities plugin loaded.

Skills:
  - /ai-utilities:skill-creator          Scaffold, rebuild, validate, and package a Claude Code skill or plugin.
  - /ai-utilities:skill-review           Security, safety, and quality review of a marketplace, plugin, or skill.
  - /ai-utilities:plan-completion-audit  Audit a plan file against the actual implementation.
  - /ai-utilities:audit-resolver         Close the audit -> fix loop on a prior report.

Commands:
  - /ai-utilities:audit-resolve          Chain plan-completion-audit -> audit-resolver.
EOF

# Emit a SessionStart system message JSON event.
ESCAPED=$(printf '%s' "$MESSAGE" | python -c 'import json,sys;print(json.dumps(sys.stdin.read()))')
printf '{"systemMessage": %s}\n' "$ESCAPED"
