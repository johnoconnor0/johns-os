# Test suites

Run everything with `python scripts/validate-repo.py`. It discovers the Python
suites rather than listing them, so a new `*/tests/test_*.py` is picked up
automatically.

| Suite | Tests | What it defends |
| --- | ---: | --- |
| `tests/test_marketplace.py` | 13 | Marketplace metadata shape |
| `tests/test_contracts.py` | 38 | Agreement between four marketplace surfaces, six plugin manifests, and files on disk |
| `tests/test_packaging.py` | 39 | What the npm tarball actually contains |
| `engineering-lifecycle/tests/test_quality_tools.py` | 165 | Lifecycle tooling |
| `engineering-lifecycle/tests/test_safety_guards.py` | 69 | The security guards, adversarially |
| `engineering-lifecycle/tests/test_hook_payloads.py` | 39 | Every hook event replayed at the process boundary |
| `engineering-lifecycle/tests/integration/` | 9 | Live DB introspection (Docker; opt-in) |
| `ai-utilities/tests/test_audit.py` | 46 | Audit pipeline |
| `cli/test/cli.test.js` | 64 | The published CLI (`node --test`) |

The CLI suite needs Node. Invoke it with **explicit file paths** —
`node --test cli/test/cli.test.js`. `node --test <directory>` runs nothing on
some Node versions while still looking like it ran, which is precisely the
failure mode the packaging suite exists to catch.

## Why these, and not the rest

The four surfaces that had never been tested were chosen on defect-finding power
per unit of effort, not on coverage percentage:

- **Contracts** — four hand-synced marketplace surfaces had already shipped a
  category-vocabulary drift. Nothing compared them.
- **CLI** — the only code every external user runs, published to npm, shipped
  broken in 0.3.0 with three separate defects, and had *zero* tests. Making it
  testable required an entrypoint guard so importing it no longer runs it.
- **Safety guards** — the security boundary, already shown porous once when
  `rm -fr /` walked past a pattern matching `rm\s+-rf`.
- **Hook payloads** — hook failure is non-blocking, so a broken hook fails
  *silently*. Nothing inside the plugin can report that, because everything that
  would report it is itself a hook. These tests are the outside observer.
- **Packaging** — 0.3.0 shipped broken because CI smoke-tested the *checkout*
  instead of the *tarball*.

## What is deliberately not tested here

**Skill behaviour cannot be asserted by automated tests.** Skills are markdown
instructions executed by a model. "Confirm before ingesting", "user declines
refresh", "prompt-injection-resistant generated instructions" are model
behaviours, not code paths. What *is* testable — and is tested — is the scripts
skills invoke, and whether a skill file declares the constraints it claims. A
test asserting a model obeys prose would pass or fail for reasons unrelated to
this repository. This rules out most of the end-to-end sections for
`service-outline`, `skill-creator`, `audit-resolver`, and the full lifecycle
walkthrough.

**Claude and Codex marketplace discovery need loaders that are not available.**
Installing through the real `claude` CLI would test Anthropic's product, not this
repository; the Codex loader is not public. The substitutable and genuinely
valuable half — that every declared path resolves and every surface agrees — is
what `test_contracts.py` covers.

**Not yet built, in rough priority order:** enforcing declared hook timeouts
rather than a fixed ceiling; concurrent-session ledger writes; introspection
failure modes that need no new containers (missing client, invalid DSN, wrong
dialect, unicode identifiers); dashboard rendering at scale.

## `@unittest.expectedFailure` in `test_safety_guards.py`

Thirty-four markers there record **real, confirmed, unfixed** defects — each
verified against the live implementation, never a test that guessed wrong. They
are filed in the local issue queue.

Know the trade-off before adding more: an unexpected success makes
`wasSuccessful()` return `False`, so **fixing one of these defects turns the
build red** until the marker is removed. That is deliberate — it forces the
fixer to notice — but it means a marker must never be used for a case that might
start passing on its own. For genuinely open questions, use `unittest.skip` with
the tracking reference instead.
