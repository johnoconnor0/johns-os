#!/usr/bin/env bash
# AI Cookbook — PreToolUse hook for Write tool
# Blocks writes to skill.md that don't include $ARGUMENTS

set -euo pipefail

# Read JSON input from stdin
INPUT=$(cat)

# Check if jq is available; if not, allow the write (graceful degradation)
if ! command -v jq &>/dev/null; then
  exit 0
fi

# Extract file path from the tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Only check files named skill.md (case-insensitive)
if [[ ! "${FILE_PATH,,}" =~ skill\.md$ ]]; then
  exit 0
fi

# Extract the content being written
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty' 2>/dev/null)

# Check for $ARGUMENTS in the content
if [ -n "$CONTENT" ] && ! echo "$CONTENT" | grep -q '\$ARGUMENTS'; then
  echo "skill.md must include \$ARGUMENTS for user input. Add a '## User Context' section with \$ARGUMENTS." >&2
  exit 2
fi

exit 0
