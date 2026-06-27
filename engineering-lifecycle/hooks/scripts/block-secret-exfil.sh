#!/usr/bin/env sh
set -eu

payload="$(cat || true)"
command="$(printf "%s" "$payload" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

case "$command" in
  *".env"*curl*|*".env"*Invoke-WebRequest*|*".env"*wget*|*"cat .env"*|*"Get-Content .env"*)
    echo "Blocked possible secret exfiltration command by Engineering Lifecycle hook." >&2
    exit 2
    ;;
esac

exit 0
