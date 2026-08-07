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

# Extract file path from the tool input. `|| exit 0` because `set -e` otherwise
# kills this script the moment jq cannot parse stdin - a payload this hook can
# neither read nor act on became an uncontrolled non-zero exit out of a
# PreToolUse gate, which is the opposite of the graceful degradation the check
# above documents. If the payload is unreadable there is nothing to lint.
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0

# Only check files named skill.md (case-insensitive). Lowercased with `tr`
# rather than `${VAR,,}`: that expansion is bash 4, and macOS ships bash 3.2,
# where it is a hard "bad substitution" parse error rather than a silent
# mismatch - so every invocation of this hook died on macOS.
LOWER_PATH=$(printf '%s' "$FILE_PATH" | tr '[:upper:]' '[:lower:]')
if [[ "$LOWER_PATH" != *skill.md ]]; then
  exit 0
fi

# Extract the content being written
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty' 2>/dev/null) || exit 0

# Check for $ARGUMENTS in the content
if [ -n "$CONTENT" ] && ! echo "$CONTENT" | grep -q '\$ARGUMENTS'; then
  echo "skill.md must include \$ARGUMENTS for user input. Add a '## User Context' section with \$ARGUMENTS." >&2
  exit 2
fi

exit 0
