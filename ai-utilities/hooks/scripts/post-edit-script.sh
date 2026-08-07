#!/usr/bin/env bash
# AI Cookbook — PostToolUse hook for Write|Edit
# Reminds about making script files executable

set -euo pipefail

INPUT=$(cat)

if ! command -v jq &>/dev/null; then
  exit 0
fi

# `|| exit 0`: `set -e` otherwise kills this script when jq cannot parse stdin,
# so a malformed payload left the hook exiting non-zero with no message at all.
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0

# Only check .py and .sh files in scripts/ directories
if [[ ! "$FILE_PATH" =~ scripts/.*\.(py|sh)$ ]]; then
  exit 0
fi

if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

# Check if file is executable
if [ ! -x "$FILE_PATH" ]; then
  jq -n --arg fp "$FILE_PATH" '{
    systemMessage: ("Reminder: " + $fp + " is not executable. Run: chmod +x \"" + $fp + "\"")
  }'
fi

exit 0
