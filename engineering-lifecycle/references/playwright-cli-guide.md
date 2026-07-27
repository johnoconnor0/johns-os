# Playwright CLI Guide

Driving a real browser from the terminal, for exploration and verification. This
is CLI-first: use it to find out what a page actually does. Do not pivot to
`@playwright/test` spec files unless the task is to author tests.

## Prerequisite

The wrapper needs `npx`, which comes with Node.js.

```bash
command -v npx >/dev/null 2>&1 && echo ok
```

If it is missing, stop and ask the user to install Node.js rather than working
around it. A global install of the CLI is optional:

```bash
npm install -g @playwright/cli@latest
```

## Wrappers

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/playwright_cli.sh" open https://example.com
```

```powershell
& "${env:CLAUDE_PLUGIN_ROOT}/scripts/playwright_cli.ps1" open https://example.com
```

Both prefer a global `playwright-cli` when present and fall back to `npx`.

## The loop

1. `open <url>` (add `--headed` when a visual check helps)
2. `snapshot` to get stable element refs
3. act on refs from **that** snapshot
4. `snapshot` again after navigation or a significant DOM change
5. capture artifacts when useful

```bash
PW="${CLAUDE_PLUGIN_ROOT}/scripts/playwright_cli.sh"
sh "$PW" open https://example.com/login
sh "$PW" snapshot
sh "$PW" fill e1 "operator@example.com"
sh "$PW" fill e2 "$TEST_PASSWORD"
sh "$PW" click e3
sh "$PW" snapshot
```

## Re-snapshot after

- navigation
- clicking anything that substantially changes the UI
- opening or closing a modal or menu
- switching tabs

Refs go stale. A command failing on a missing ref means take a new snapshot; it
does not mean the element is gone.

## Common commands

| Command | Purpose |
| --- | --- |
| `open <url> [--headed]` | Navigate |
| `snapshot` | Accessibility tree with element refs |
| `click <ref>` / `fill <ref> <text>` / `type <text>` / `press <key>` | Interact |
| `screenshot [--full-page]` | Capture an image |
| `tracing-start` / `tracing-stop` | Record a trace for debugging |
| `tab-new <url>` / `tab-list` / `tab-select <n>` | Multi-tab work |
| `pdf` | Print to PDF |

## Guardrails

- **Always snapshot before referencing a ref like `e12`.** If you do not have a
  fresh snapshot, say so and use a placeholder ref rather than guessing.
- Prefer explicit commands over `eval` and `run-code`. Reaching for arbitrary
  JavaScript to bypass a stale ref hides the real problem.
- Put artifacts under the initiative's `testing/playwright/`. Do not create new
  top-level output folders.
- **Never type real credentials.** Use environment variables or test accounts, and
  never paste a secret into a command that will be logged.
- `--headed` for visual checks; headless otherwise, because it is faster and works
  in CI.

## When to write specs instead

Move to `@playwright/test` spec files when the goal is a check that runs
repeatedly: a regression suite, a CI gate, a smoke test after deploy. Use the CLI
when the goal is to find out what happens.

`references/e2e-patterns.md` covers writing the specs.
