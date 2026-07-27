# Drive a real browser from the terminal without requiring a global install.
#
# PowerShell twin of playwright_cli.sh. This repo is Windows-primary, so shipping
# only the POSIX wrapper would mean the documented commands do not run on the
# machine most of this work happens on.
#
# Usage:
#   .\playwright_cli.ps1 open https://example.com --headed
#   .\playwright_cli.ps1 snapshot
#   .\playwright_cli.ps1 click e15
#
# The workflow is always: open -> snapshot -> act on refs from that snapshot ->
# re-snapshot after navigation or a significant DOM change.

$ErrorActionPreference = 'Stop'

if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    Write-Error "npx not found. Install Node.js (which provides npx), then re-run."
    exit 127
}

$global = Get-Command playwright-cli -ErrorAction SilentlyContinue
if ($global) {
    & playwright-cli @args
    exit $LASTEXITCODE
}

& npx --yes --package '@playwright/cli' playwright-cli @args
exit $LASTEXITCODE
