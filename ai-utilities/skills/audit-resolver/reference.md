# Audit Resolver — Reference Material

## Finding Category → Handling Strategy

Used in Phase 2 triage. A structured audit already carries `family`, `rule` and `route` on every finding, so this table is the fallback for a legacy markdown report and the reference for overriding a suggested strategy.

| Category | Default strategy | Notes |
|----------|------------------|-------|
| `type-error` | AUTO | Run `tsc --noEmit` after; should drop the specific error |
| `lint` | AUTO | Use the project's ESLint config; never `--fix` blindly — Edit only the flagged lines |
| `unused-import` | AUTO | Edit + verify no remaining references via Grep |
| `dead-code` | AUTO | Edit + verify no remaining references via Grep |
| `dead-export` | AUTO | Edit + verify no consumers via Grep |
| `dangling-ref` | AUTO | Remove or fix the broken link; verify the new path exists |
| `doc-drift` | AUTO | Update text to current state; verify against ground-truth (e.g. `find` counts) |
| `convention` | AUTO | Frontmatter / heading-depth / paths-glob fixes |
| `dep-update` | AUTO | `npm install <pkg>@<ver>` then re-run `npm audit` |
| `missing-feature` | PLAN-FIRST | Feature work needs a real plan |
| `security` | PLAN-FIRST | Security fixes are judgement-heavy; always review |
| `bug` | PLAN-FIRST | Bugs need root-cause analysis, not symptom-patches |
| `structure` (god-file split, refactor) | PLAN-FIRST | Multi-file move; needs design |
| `db-schema` / `migration` / `index` / access-control | DELEGATE → `engineering-lifecycle:database-engineer` | Model-level work goes to the `create-data-model` skill instead |
| `api-contract` | DELEGATE → `engineering-lifecycle:api-contract-reviewer` | Contract changes go to the `create-api-contract` skill |
| `test-gap` | DELEGATE → `engineering-lifecycle:qa-test-strategist` | New suites go to the `create-test-strategy` skill |
| `release` / `ci` / `deployment` | DELEGATE → `engineering-lifecycle:devops-release-engineer` | |
| `hygiene` / `dangling-ref` at scale | DELEGATE → `engineering-lifecycle:repo-hygiene-maintainer` | Or the `update-repo-hygiene` skill |
| `human-decision` (descope / pattern-choice / approval) | HUMAN-INPUT | Audit explicitly flagged as needing user input |
| `suggestion-only` (cosmetic) | DEFER (unless `--severity=suggestion`) | |

Every target above is an agent or skill this marketplace ships. **Check availability
at run time** rather than assuming it: if the plugin is not installed, fall back to
the `general-purpose` agent and record the downgrade in the ledger. Never tell the
user to install a plugin from a marketplace other than the one they are running.

### How to detect category from a finding

1. Use the finding's own `family`, `rule` and `route` fields. A structured audit
   emits them, so nothing here needs to be inferred.
2. Only when those are absent — an older markdown-only report — fall back to:
   - the file extension: `*.sql` or a migrations directory → `db-schema`; `*.md` → `doc-drift`
   - descriptor keywords: "missing", "broken", "unused", "stale", "deprecated", "dangling"

---

## Verifier selection

Used by `scripts/verify.py` to pick the right verifier between batches. Run it with `--dry-run` to see the choice and the reason without executing anything.

### Order of detection

First match wins for the primary verifier.

1. **A single repository-wide validation entrypoint, if the repo has one.** Some
   repositories deliberately expose one command that runs everything — this one does,
   as `python scripts/validate-repo.py`. When such a script exists it *is* the
   verifier, and no stack guessing is needed or wanted.
2. **The repository's own recorded test commands.** If a lifecycle workspace exists,
   `.project/.engineering/context/stack.json` carries a `test_commands` map that was
   resolved against what the project actually declares. Prefer it over re-deriving
   commands from file presence, which is how a verifier comes to advertise a script
   the project does not have.
3. **File-presence detection**, as a last resort.

| Detection signal (file present) | Stack | Verifier command |
|---|---|---|
| `package.json` with a `build` script and a TypeScript config | Next.js / React / generic TS | `npx tsc --noEmit && npm run build` |
| `package.json` with a `test` script | Generic Node | `npm test` |
| `pyproject.toml` with a mypy section | Python (typed) | `mypy . && python -m pytest` |
| `pyproject.toml`, no mypy config | Python (untyped) | `python -m pytest`, or `python -m unittest discover` when no pytest is installed |
| `Cargo.toml` | Rust | `cargo check && cargo test` |
| `go.mod` | Go | `go vet ./... && go test ./...` |
| A migrations directory and a database client on PATH | SQL project | The dialect's lint command, if it has one |
| Multiple (monorepo) | Mixed | Run each detected verifier; aggregate pass/fail |
| None detected | Unknown | Manual review only — mark fixes "applied unverified" |

Always add a discovered test directory as a secondary verifier.

---

## Delegation map

Used when a finding is handled by dispatching an agent or another skill. Every entry
names something this marketplace ships; confirm it is installed before dispatching.

| Target | Kind | Finding pattern | What to hand it |
|---|---|---|---|
| `engineering-lifecycle:database-engineer` | agent | Missing access-control policy, missing index on a foreign key, unsafe migration | The table, the access model, and the write volume |
| `engineering-lifecycle:create-data-model` | skill | The model and the shipped migrations disagree; the entity model is stale | The schema source and the drift report |
| `engineering-lifecycle:api-contract-reviewer` | agent | A caller references an endpoint or field the contract does not define | The contract and the call site |
| `engineering-lifecycle:create-api-contract` | skill | The contract itself is missing or incomplete | The consumers and the intended shape |
| `engineering-lifecycle:qa-test-strategist` | agent | A behaviour changed with no test covering it | The change and the risk it carries |
| `engineering-lifecycle:create-test-strategy` | skill | No test plan exists for an area under change | The feature and its acceptance criteria |
| `engineering-lifecycle:security-reviewer` | agent | Secret handling, authorisation, dependency risk | The finding and the surrounding code |
| `engineering-lifecycle:devops-release-engineer` | agent | Release sequencing, rollback, environment config | The change and its deployment path |
| `engineering-lifecycle:repo-hygiene-maintainer` | agent | Dead references, generated-artifact drift, docs drift | The checker output |
| `engineering-lifecycle:solution-architect` | agent | Structural change spanning several modules | The current shape and the constraint |
| `engineering-lifecycle:create-engineering-plan` then `engineering-lifecycle:implement-feature-safely` | skills | `missing-feature` — real feature work | The requirement and the affected files |
| `engineering-lifecycle:review-change` | skill | Post-batch verification of a large diff | The diff |

---

## Batch Sizing Heuristics

- Default max batch size: **10 findings**
- For AUTO findings clustered by file: include all findings in that file (often more than 10 — single Edit pass is cheaper than multiple)
- For PLAN-FIRST: **1 finding per batch** (avoid plan interactions)
- For DELEGATE: **1 finding per batch** (the dispatched output is the unit of work)
- For HUMAN-INPUT: **1 finding per batch** (each needs full user attention)

---

## Common Failure Modes

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| A legacy markdown report converted incompletely | It predates `findings.json`, so it is read heuristically | The summary reports `unconverted_rows`. Re-run the audit to get a structured report rather than trusting the conversion |
| Verifier fails after a batch | A fix caused an unintended type / lint cascade | Halt; revert the batch; re-classify the finding as PLAN-FIRST |
| A delegated agent or skill returns nothing useful | Its plugin is not installed, or it needed different input | Mark deferred, name the plugin, and say which marketplace the user is running. Do not invent an install command |
| Ledger grows huge (50+ findings) | Audit covered too much ground | Use `--severity` to focus; resume with the rest later |
| Re-audit shows new findings | Edits introduced regression | Diff the new vs old report; address regressions before declaring done |
| Conflicting fixes (one Edit undoes another) | Dependency graph missed an edge | Halt; re-triage with explicit ordering |
| User says "stop" mid-execution | Ran out of time or context shifted | Write ledger as-is; resume later by re-invoking |

---

## Resumability

The ledger at `.project/audits/audit-resolver/<date>/audit-resolver-ledger.md` **is the
resume state**. On re-invocation against the same original audit report:

1. Read the existing ledger
2. Skip any finding ID already listed in the Execution Log with outcome "closed"
3. Continue with findings in the Phase 1 inventory that are not yet in the Execution Log
4. Append new execution rows; never rewrite history

This makes the workflow safe to interrupt — if a `git stash pop` or context switch is needed, just exit and re-invoke later.
