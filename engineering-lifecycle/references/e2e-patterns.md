# E2E Patterns

Writing end-to-end tests that stay useful. The failure mode for E2E is not
"missing coverage", it is a suite so slow and flaky that people stop reading it.

## What belongs in E2E

Only journeys where the integration is the risk: the parts where a unit test
cannot tell you the truth because the answer depends on the browser, the network,
and the server agreeing.

| Test at this level | Reason |
| --- | --- |
| Sign in, sign out, session expiry | Auth spans client, server and cookies |
| The primary money path (checkout, submit, publish) | Where failure costs most |
| A permission boundary | That role A cannot see role B's data is worth proving end to end |
| A multi-step flow with real persistence | Wizards, uploads, anything with state between pages |

**Not** in E2E: field validation rules, formatting, copy, edge cases in a pure
function, every permutation of a form. Those are unit or component tests, and
putting them here is what makes a suite take forty minutes.

A good target is five to fifteen E2E specs for a typical product. If you have
sixty, most of them belong a level down.

## Selectors

In priority order:

1. **Role and accessible name** — `getByRole('button', { name: 'Export' })`.
   Couples the test to what a user perceives, which is what you actually want to
   protect, and it fails when accessibility breaks.
2. **Label text** — `getByLabel('Email')` for form fields.
3. **`data-testid`** — for things with no accessible identity, like a chart canvas.

Never select by CSS class or DOM structure. Those change for styling reasons and
the resulting failure teaches you nothing.

## Waiting

- **Never `waitForTimeout`.** A fixed sleep is either too short (flaky) or too
  long (slow), and it is usually both on different machines.
- Playwright's assertions auto-wait. `await expect(locator).toBeVisible()` retries
  until the timeout, which is almost always what you meant.
- Wait for a **condition**, not a duration: a response, a URL, an element state.

## Test data

The most common source of flake is tests sharing state.

- Each spec creates the data it needs and cleans up after itself, or runs against
  a fresh database.
- Never depend on data another spec created. That makes the suite order-dependent
  and unable to run in parallel.
- Seed through an API or a fixture, not through the UI. Signing in via the login
  form in every spec is slow and tests the same thing repeatedly. Sign in once,
  save storage state, reuse it.

```ts
// playwright.config.ts
projects: [
  { name: 'setup', testMatch: /auth\.setup\.ts/ },
  { name: 'chromium', dependencies: ['setup'], use: { storageState: '.auth/user.json' } },
]
```

## Structure

```ts
test('a tenant admin exports only their own audit events', async ({ page }) => {
  await page.goto('/audit');
  await page.getByLabel('From').fill('2026-01-01');
  await page.getByRole('button', { name: 'Export' }).click();

  const download = await page.waitForEvent('download');
  expect(download.suggestedFilename()).toMatch(/audit-\d{4}-\d{2}-\d{2}\.csv/);
});
```

- One journey per spec. A spec asserting six unrelated things tells you almost
  nothing when it fails.
- Name the spec after the user outcome, not the mechanism. "exports only their own
  audit events" survives a rewrite; "clicks the export button" does not.

## Flake

A flaky test is worse than no test: it trains people to re-run rather than
investigate.

- **Never `test.retry` as a fix.** Retries hide the cause. Use them only to
  tolerate genuinely external instability, and record why.
- Quarantine a flaky spec (skip it with a linked issue) rather than leaving it
  failing intermittently in the main suite.
- Common causes, in order: fixed sleeps, shared state, animations not settling,
  time-dependent data, and tests that assume a fresh database when the previous
  run left rows behind.

## In CI

- Run against a built artifact, not a dev server. A dev server has different
  timing, different bundling, and sometimes different code.
- Record trace, video and screenshot **on first retry only**. Recording always is
  slow and produces gigabytes nobody looks at.
- Shard across workers when the suite exceeds a few minutes.
- Publish the HTML report as an artifact so a failure can be diagnosed without
  reproducing locally.

```ts
use: { trace: 'on-first-retry', screenshot: 'only-on-failure', video: 'retain-on-failure' }
```

## Accessibility

E2E is the level where an accessibility check is cheap, because the page is
already rendered:

```ts
const results = await new AxeBuilder({ page }).analyze();
expect(results.violations).toEqual([]);
```

Add it to the specs covering the main journeys rather than writing separate
accessibility specs.
