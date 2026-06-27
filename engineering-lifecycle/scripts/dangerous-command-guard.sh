#!/usr/bin/env sh
set -eu

payload="$(cat || true)"
command="$(printf "%s" "$payload" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

case "$command" in
  *"rm -rf /"*|*"rm -rf ."*|*"git reset --hard"*|*"git clean -fdx"*|*"docker system prune"*|*"drop database"*|*"truncate table"*|*"chmod -R 777"*)
    echo "Blocked dangerous shell command by Engineering Lifecycle hook." >&2
    exit 2
    ;;
esac

printf '%s\n' '{"blocked": false}'
exit 0
