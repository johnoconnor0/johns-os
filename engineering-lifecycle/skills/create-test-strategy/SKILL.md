---
name: create-test-strategy
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*), Bash(npx:*), Bash(sh:*), Bash(pwsh:*)
description: Use to define the automated and manual test plan for a product, feature, change, migration, release, or risk area, and to author the E2E specs. Can drive a real browser from the terminal via the Playwright CLI to verify behaviour before writing tests about it.
argument-hint: "[--explore <url>] [--e2e] [--strategy-only]"
---

# Create Test Strategy

## Trigger

Use when the user asks what to test, how to verify a feature, which test types are
needed, how to reduce release risk, or to write E2E tests.

## When To Use

- Before or after implementation.
- Before release planning.
- When risk profile or coverage expectations are unclear.
- When a user journey needs an automated regression check.

## Verify Before You Specify

A test strategy written only from reading code describes what the code appears to
do. Where a real browser is available, look at the actual behaviour first: the gap
between intended and actual is usually where the useful tests are.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/playwright_cli.sh" open http://localhost:3000 --headed
sh "${CLAUDE_PLUGIN_ROOT}/scripts/playwright_cli.sh" snapshot
```

On Windows use `scripts/playwright_cli.ps1`. Both wrap
`npx --package @playwright/cli playwright-cli`, so no global install is needed;
they fail with a clear message if `npx` is absent.

The loop is `open` → `snapshot` → act on refs from that snapshot → re-snapshot
after navigation or a significant DOM change. Refs go stale. Read
`references/playwright-cli-guide.md` before the first command.

Skip this when there is no running app, when the change is not user-facing, or
when the user asks for a plan only.

## Workflow

1. **Inspect** existing tests, package scripts, CI config, risk areas and
   acceptance criteria. `context/stack.json` records the detected test tooling
   under `testing` and the real commands under `test_commands`; use those rather
   than guessing the runner.
2. **Explore the running app** with the Playwright CLI where one exists, and
   record what you observed. Note behaviour that differs from the PRD: that is a
   finding, not a test.
3. **Classify required coverage** across unit, integration, contract, E2E,
   regression, migration, load, security and manual QA. Push each check to the
   cheapest level that can actually prove it. A validation rule tested through the
   browser is a slow test of a fast thing.
4. **Tie every recommended test** to a user-facing behaviour, a failure mode, or
   an implementation slice. A test with no stated reason gets deleted by whoever
   inherits it.
5. **Select the E2E journeys.** Only where the integration is the risk: auth, the
   primary money path, a permission boundary, a multi-step flow with real
   persistence. Five to fifteen specs is a healthy number for a product; sixty
   means most belong a level down. Read `references/e2e-patterns.md`.
6. **Author the specs** (unless `--strategy-only`). Selectors by role and
   accessible name first, then label, then `data-testid`. Never by CSS class.
   Never `waitForTimeout`. One journey per spec, named after the user outcome.
7. **Identify gates**: what must pass before merge, before release, and after
   release. These are different lists.
8. **Record manual QA** that is not practical to automate yet, and why.
9. **Run what you can**, and report the actual result. Never claim a test passed
   unless it was run.
10. Validate:

    ```bash
    python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" <artifact paths>
    ```

## Arguments

| Flag | Effect |
| --- | --- |
| `--explore <url>` | Drive the browser against this URL before planning. |
| `--e2e` | Author E2E specs as well as the strategy document. |
| `--strategy-only` | Plan only. Write no spec files. |

## Outputs

- `.project/.engineering/initiatives/<initiative-id>/testing/test-strategy.md`
- `.project/.engineering/initiatives/<initiative-id>/testing/e2e-plan.md` (journeys,
  selectors, data setup, gates) when E2E is in scope
- E2E specs in the repo's own test location (`e2e/`, `tests/e2e/`, or wherever the
  project already keeps them)
- Exploration artifacts under
  `.project/.engineering/initiatives/<initiative-id>/testing/playwright/`

Do not create new top-level artifact folders.

## Required Front Matter

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

## Required Sections

- Coverage
- Scenarios
- Manual QA
- Required Commands
- Release Gates

## Safety Constraints

- **Never claim a test passed unless it was run.** Report the actual output.
- Scale coverage to risk and blast radius. Exhaustive E2E is a cost, not a virtue.
- Never type real credentials into a browser command. Use environment variables or
  a test account.
- Never drive a browser against production without explicit approval. Read-only
  looks fine; a form submission is not.
- Do not add test dependencies the repo does not already have without saying so.
- Record residual risk where verification could not be completed.

## Related Agents

- `qa-test-strategist`
- `frontend-engineer`
- `backend-engineer`
- `security-reviewer`
