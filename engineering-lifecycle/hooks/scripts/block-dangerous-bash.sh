#!/usr/bin/env sh
set -eu

payload="$(cat || true)"
command="$(printf "%s" "$payload" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

case "$command" in
  *"rm -rf /"*|*"git reset --hard"*|*"git clean -fdx"*|*"Remove-Item -Recurse -Force C:\\"*|*"format c:"*)
    echo "Blocked dangerous shell command by Engineering Lifecycle hook." >&2
    exit 2
    ;;
esac

exit 0
