# Audit Resolver — Reference Material

## Finding Category → Handling Strategy

Used in Phase 2 triage. Maps the inferred category (from finding text + file extension + phase) to the default handling strategy.

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
| `db-schema` / `migration` / `rls` / `index` | SUB-SKILL → `engineering/database-design:*` | Route to the right sibling skill |
| `experiment-design` / `power-analysis` | SUB-SKILL → `data-science/experimentation:ab-test-designer` | |
| `forecast-spec` | SUB-SKILL → `data-science/experimentation:forecasting-model-spec` | |
| `pricing` / `unit-economics` / `cost-structure` | SUB-SKILL → `economics/business-economics:*` | |
| `moat` / `competitive-dynamics` / `elasticity` | SUB-SKILL → `economics/strategic-economics:*` | |
| `human-decision` (descope / pattern-choice / approval) | HUMAN-INPUT | Audit explicitly flagged as needing user input |
| `suggestion-only` (cosmetic) | DEFER (unless `--severity=suggestion`) | |

### How to detect category from a finding

1. Check the finding's own "category" or "type" field if present
2. Look at file extension: `*.ts`/`*.tsx` → likely type-error or lint; `*.sql`/`migrations/*` → db-schema; `*.md` → doc-drift
3. Look at the audit phase the finding came from:
   - Phase 2 (Type Safety) → type-error / lint
   - Phase 3 (Bug & Logic) → bug
   - Phase 4 (Code Structure) → structure
   - Phase 5 (Failsafes) → bug / structure
   - Phase 6 (Security) → security
   - Phase 7 (Feature Hardening) → bug / structure / missing-feature
   - Phase 8 (Deprecated Cleanup) → dead-code / dead-export / dep-update
   - Phase 10 (Supabase) → db-schema / rls / migration
   - Phase 11 (FE↔BE Alignment) → bug or db-schema
4. Look at descriptor keywords: "missing", "broken", "unused", "stale", "deprecated", "dangling"

---

## Verifier Matrix (per detected stack)

Used by `scripts/verify-stack.sh` to pick the right verifier between batches.

| Detection signal (file present) | Stack | Verifier command |
|---|---|---|
| `package.json` with `"build"` script + `tsconfig.json` | Next.js / React / generic TS | `npx tsc --noEmit && npm run build` |
| `package.json` with `"test"` script | Generic Node | `npm test` |
| `pyproject.toml` + `mypy.ini` (or `[tool.mypy]`) | Python (typed) | `mypy . && python -m pytest` |
| `pyproject.toml` + no mypy config | Python (untyped) | `python -m pytest` |
| `requirements.txt` only | Python (older) | `python -m pytest` if `tests/` exists |
| `Cargo.toml` | Rust | `cargo check && cargo test` |
| `go.mod` | Go | `go vet ./... && go test ./...` |
| `scripts/check-versions.mjs` | Web Lifter plugin marketplace | `node scripts/check-versions.mjs` + `python tests/scripts/test_smoke.py` if `tests/` exists |
| `supabase/migrations/` + `supabase` CLI on PATH | Supabase project | `supabase db lint` (if available) |
| Multiple (monorepo) | Mixed | Run each detected verifier; aggregate pass/fail |
| None detected | Unknown | Manual review only — mark fixes "applied unverified" |

### Order of detection

Check in this order (first match wins for primary verifier; secondary verifiers also run if relevant):

1. `scripts/check-versions.mjs` → plugin marketplace
2. `package.json` → JS/TS
3. `pyproject.toml` / `requirements.txt` → Python
4. `Cargo.toml` → Rust
5. `go.mod` → Go
6. Fall through → "unknown"

Always add `tests/` discovery as a secondary verifier if a tests directory exists.

---

## Per-Sub-Skill Dispatch Map

Used when a finding maps to a sub-skill and `Agent` invocation is needed.

| Plugin:skill | Finding pattern | Agent invocation hint |
|--------------|----------------|----------------------|
| `engineering/database-design:rls-policy-designer` | "missing RLS policy", "RLS not enabled", "auth.uid() not referenced" | Provide the table name + access model; ask for the policy SQL |
| `engineering/database-design:migration-plan-builder` | "schema change with > 1M rows affected", "NOT NULL added to existing column" | Provide the change description + write volume |
| `engineering/database-design:index-strategy-planner` | "missing index on FK", "seq scan in EXPLAIN" | Provide the slow query + table size |
| `engineering/database-design:erd-generator` | "ERD missing / stale" | Provide schema source |
| `data-science/experimentation:ab-test-designer` | "experiment design hole", "no power analysis" | Provide the primary metric + baseline |
| `data-science/experimentation:forecasting-model-spec` | "forecast missing validation", "no baseline beat" | Provide series + horizon |
| `data-science/experimentation:causal-impact-analyser` | "claim made without identifying assumption" | Provide intervention + outcome |
| `economics/business-economics:pricing-architecture-designer` | "pricing model unclear" | Provide product + segments |
| `economics/business-economics:cost-structure-builder` | "cost classification missing" | Provide business snapshot |
| `economics/strategic-economics:moat-strength-audit` | "moat claim without scoring" | Provide business + competitors |

---

## Batch Sizing Heuristics

- Default max batch size: **10 findings**
- For AUTO findings clustered by file: include all findings in that file (often more than 10 — single Edit pass is cheaper than multiple)
- For PLAN-FIRST: **1 finding per batch** (avoid plan interactions)
- For SUB-SKILL: **1 finding per batch** (sub-skill output is the unit of work)
- For HUMAN-INPUT: **1 finding per batch** (each needs full user attention)

---

## Common Failure Modes

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| Audit report parse missing some findings | Markdown structure non-standard (unusual section headings) | Run `parse-audit-report.sh` in verbose mode; fall back to manual extraction |
| Verifier fails after a batch | A fix caused an unintended type / lint cascade | Halt; revert the batch; re-classify the finding as PLAN-FIRST |
| Sub-skill returns nothing useful | Plugin not installed or sub-skill needs different input | Mark as deferred; suggest `/plugin install <name>` |
| Ledger grows huge (50+ findings) | Audit covered too much ground | Use `--phase=N` to focus; resume with remaining phases later |
| Re-audit shows new findings | Edits introduced regression | Diff the new vs old report; address regressions before declaring done |
| Conflicting fixes (one Edit undoes another) | Dependency graph missed an edge | Halt; re-triage with explicit ordering |
| User says "stop" mid-execution | Ran out of time or context shifted | Write ledger as-is; resume later by re-invoking |

---

## Resumability

The ledger at `.project/audits/<date>/audit-resolver-ledger.md` **is the resume state**. On re-invocation against the same original audit report:

1. Read the existing ledger
2. Skip any finding ID already listed in the Execution Log with outcome "✓ closed"
3. Continue with findings in Phase 1 inventory that aren't yet in the Execution Log
4. Append new execution rows; never rewrite history

This makes the workflow safe to interrupt — if a `git stash pop` or context switch is needed, just exit and re-invoke later.
