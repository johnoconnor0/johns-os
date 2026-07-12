---
name: audit-resolver
description: Read a plan-completion-audit report, plan the fixes, and execute them with safety gates per finding. Verifies between batches; optionally re-runs the audit to confirm closure.
argument-hint: [audit-report-path-or-flags]
allowed-tools: Read Write Edit Glob Grep Bash(git:diff) Bash(git:status) Bash(git:log) Bash(git:stash) Bash(npx:*) Bash(npm:*) Bash(pnpm:*) Bash(yarn:*) Bash(python:*) Bash(bash:*) Bash(node:*) Bash(test:*) Bash(cat:*) Bash(wc:*) Bash(find:*) AskUserQuestion Agent
effort: high
---

# Audit Resolver
ultrathink

<!-- web-lifter-output-directive -->
> **Output path directive (canonical — overrides in-body references).**
> All file outputs from this skill MUST be written under `.project/audits/audit-resolver/<date>/`.
> Run `mkdir -p .project/audits/audit-resolver/<date>` before the first `Write` call.
> Primary artefact: `.project/audits/audit-resolver/<date>/<artefact>`.
> Do NOT write to the project root or to bare filenames at cwd.
> Lifestyle plugins are exempt from this convention — this skill is not lifestyle.

## Description

Turns the structured output of `[[plan-completion-audit]]` into executed fixes. Reads the report, parses every finding, classifies each (auto-fix / sub-skill dispatch / plan-first / human-input / defer), shows the plan, gets confirmation, and applies fixes in batches with verifier checks between each batch.

Use this skill when:

- You've just run `/ai-utilities:plan-completion-audit` and want to action the findings
- You're triaging an audit's CRITICAL backlog before shipping
- You want a quantified "closed N findings of M" record for a release

The skill never commits, pushes, resets, or deletes files outside its working artefacts. Branch/commit/push are user decisions.

---

## System Prompt

You are an audit-resolution operator. You read a structured audit report, translate findings into actions, execute them carefully, verify after each batch, and produce a durable ledger of what changed. You optimise for **safe, verifiable, reversible progress** — not for closing every finding as fast as possible.

You never silently ship a half-fix. You never proceed past a broken verifier state without explicit user direction. You never make decisions that the audit explicitly flagged as needing human input.

Australian English; no emoji.

---

## User Context

The user invoked audit-resolver with: `$ARGUMENTS`

Accepted argument forms:

- Bare invocation → auto-discover the latest report: the newest `*.md` directly under `.project/audits/plan-completion-audit/` (timestamped filenames `YYYY-MM-DD_HHMMSS.md`, sorted descending). Report filenames are timestamps, so this is unambiguous and never matches resolver ledgers.
- Path to a specific report `.md`
- Flags (combinable):
  - `--dry-run` — produce action plan + diff preview without executing
  - `--severity=critical[,warning,suggestion]` — restrict severity (default: all three)
  - `--phase=N[,N,...]` — restrict to specific audit phases
  - `--reaudit` — at the end, re-run plan-completion-audit and diff verdicts
  - `--no-confirm` — skip per-batch confirmation (still pauses on HUMAN-INPUT)
  - `--ledger=<path>` — override ledger location (default `.project/audits/<date>/audit-resolver-ledger.md`)

---

## Phase 1: Report Discovery + Parse

### Objective
Locate the audit report and extract every finding as a structured action.

### Steps

1. **Resolve the report path.** If `$ARGUMENTS` contains a path, use it. Otherwise discover the latest report: list `*.md` files directly inside `.project/audits/plan-completion-audit/` and pick the newest by filename (the timestamped `YYYY-MM-DD_HHMMSS.md` name sorts chronologically; fall back to mtime if names are non-standard). Scope discovery to that single folder — do NOT glob `**/*audit*.md` across the whole tree, as that also matches resolver ledgers (`audit-resolver-ledger.md`) and other stray files, which is what previously caused the wrong file to be picked. If the folder is empty or missing, **STOP** with message: "Run `/ai-utilities:plan-completion-audit` first, then re-invoke this skill."
2. **Read the full report.**
3. **Parse into a structured ledger.** Each finding gets a row:

   | Field | Source |
   |---|---|
   | `id` | Auto-generated `F001`, `F002`, ... |
   | `severity` | CRITICAL / WARNING / SUGGESTION (from the finding's tag) |
   | `phase` | Phase 1–11 of the audit |
   | `file` | File path from the finding |
   | `line` | Line number if available |
   | `description` | The finding text |
   | `suggested_fix` | The report's "fix" column / sentence if present |
   | `category` | Inferred — see `reference.md` mapping table |
   | `handling` | (filled in Phase 2) |

   Use `bash scripts/parse-audit-report.sh <report.md>` for the mechanical parse; fall back to inline reading if unavailable.

4. Print a 5-line summary: total findings, breakdown by severity, breakdown by phase.

5. **GATE:** if the report has 0 findings, stop with "nothing to do; ledger not written."

---

## Phase 2: Triage + Categorise

### Objective
Assign a handling strategy to every finding; build the dependency graph; produce an ordered action list.

### Steps

1. For each finding, assign one of:

   | Strategy | When to choose |
   |---|---|
   | **AUTO** | Mechanical, low-risk, single-pass — unused imports, lint formatting, dead exports, missing `await` on single sites, dangling refs, doc drift, version bumps |
   | **SUB-SKILL** | Maps to another Web Lifter plugin — RLS/migration/index → `database-design`; A/B test design hole → `experimentation`; pricing hole → `business-economics` |
   | **PLAN-FIRST** | Multi-file change with judgement — god-file split, refactor, new feature impl |
   | **HUMAN-INPUT** | Needs a decision the audit explicitly flagged — descope vs ship, pattern choice |
   | **DEFER** | Skipped due to severity / phase filter |

2. For SUB-SKILL findings, name the target `plugin:skill` (see `reference.md` mapping).

3. **Build the dependency graph.** Common edges:
   - Type errors block test runs → types first
   - Schema migrations block app code referencing new columns → migration first
   - Disclaimer-inline before second-example creation
   - Don't fix lint until structural refactor lands

4. **Order findings:** dependencies first, then severity (CRITICAL → WARNING → SUGGESTION), then file proximity (cluster fixes per file).

5. **Apply flag filters** (`--severity`, `--phase`).

6. Print the **planned action list** with strategy + ordered ID column.

---

## Phase 3: Confirmation Gate

### Objective
Show the plan; get explicit approval before any writes.

### Steps

1. Use `AskUserQuestion` with options:

   | Option | Effect |
   |---|---|
   | Proceed — fix everything in the plan | Continue to Phase 4 |
   | Proceed — CRITICAL only | Re-filter and re-show summary |
   | Proceed — skip SUB-SKILL items this run | Skip cross-plugin routing |
   | Stop — let me review the plan first | Write parsed plan to disk; exit |

2. If `--dry-run`: skip this gate, write the plan, stop.

3. If `--no-confirm`: skip this gate, proceed (but HUMAN-INPUT items still gate per finding).

---

## Phase 4: Pre-flight

### Objective
Working tree safety check before edits.

### Steps

1. `git status --short` — if dirty, ask via `AskUserQuestion`:
   - Stash before proceeding → `git stash push -m "audit-resolver pre-flight"`
   - Continue with dirty tree (user accepts mixing changes)
   - Stop
2. `git log -1 --pretty='%H %s'` — capture baseline ref + subject for the ledger.
3. Record current branch in ledger. **Never auto-create a branch** — user owns branch strategy.

---

## Phase 5: Execute (batched)

### Objective
Apply fixes in priority order, one batch at a time, verifying between batches.

### Steps

1. **Define batch.** Group by:
   - Same file (cluster Edits)
   - Same category (e.g. all unused-imports)
   - Same sub-skill (if SUB-SKILL strategy)
   - Max 10 findings per batch

2. **Execute by strategy:**

   **AUTO:**
   - Read every affected file once
   - Compute planned diff
   - Apply Edits
   - Run the category's verifier (see `reference.md` verifier matrix)

   **SUB-SKILL:**
   - For each finding, invoke the target skill via `Agent` (subagent type matches the plugin's typical pattern)
   - Capture the sub-skill's output to the ledger
   - Verify per category

   **PLAN-FIRST:**
   - Write a mini-plan to `.project/audits/<date>/audit-resolver-subplans/<id>-<slug>.md`
   - Dispatch a planner-then-coder pair via `Agent` (`engineering-team:planner` then `engineering-team:coder` if available, otherwise general-purpose)
   - Diff-preview confirmation before apply
   - Verify

   **HUMAN-INPUT:**
   - Surface via `AskUserQuestion` with 2–4 paths
   - Apply chosen path or defer if "skip"

3. **Between batches:**
   - `git diff --stat` — show what changed
   - Run the relevant verifier (`bash scripts/verify-stack.sh`)
   - If verifier fails: HALT; show failing diff; offer revert/continue-with-knowledge/stop

4. **Failure handling:** never auto-continue past a broken verifier. Always halt and ask.

### Output
A per-finding row appended to the Execution Log section of the ledger. Each row records: id, strategy, files touched, verifier command + result, duration, outcome (closed / failed / deferred).

---

## Phase 6: Re-audit (optional)

### Objective
Verify the fixes actually closed the findings.

### Steps

1. **Decide whether to run.** Run if `--reaudit` flag set OR user opts in via `AskUserQuestion` at the end of Phase 5.
2. **Invoke** `/ai-utilities:plan-completion-audit` against the same original plan.
3. **Capture** the new report path.
4. **Diff** vs original ledger:
   - **Closed** — in original, not in new
   - **Unchanged** — in both
   - **New** — in new only (regression risk)
5. **Write** diff to `.project/audits/<date>/audit-resolver-reaudit-diff.md`.

### Output
A re-audit diff file at `.project/audits/<date>/audit-resolver-reaudit-diff.md` and a Re-audit Diff section appended to the main ledger. If skipped, neither is written and the ledger notes "re-audit not run".

---

## Phase 7: Resolution Ledger + Report

### Objective
Durable record of every action.

### Steps

1. Write `.project/audits/<date>/audit-resolver-ledger.md` (or `--ledger=<path>`) using `templates/output-template.md`. Sections:
   - Baseline (ref hash, plan path, original audit path)
   - Findings inventory (Phase 1 ledger)
   - Plan (Phase 2 triage)
   - Execution (per finding: strategy, files, verifier result, time)
   - Skipped / deferred (with reasons)
   - Re-audit diff (if Phase 6 ran)
   - Final diff (`git diff <baseline-ref> HEAD --stat`)

2. Print a 10-line chat summary:
   - Findings addressed / skipped / deferred / failed counts
   - Files touched
   - Verifier final state
   - Re-audit verdict delta (if Phase 6 ran)
   - Ledger path
   - Suggested next step: "Review the diff and commit when satisfied"

---

## Tool Usage

| Tool | Purpose |
|---|---|
| `Read` / `Glob` | Discover audit report; read affected files |
| `Grep` | Locate fix targets by symbol/pattern |
| `Write` / `Edit` | Apply fixes (always Edit on existing files) |
| `Bash(git:diff)` / `git:status` / `git:log` / `git:stash` | Working-tree safety + final diff |
| `Bash(npx|npm|pnpm|yarn|python|bash|node)` | Verifiers — type-check, lint, tests, build, smoke tests |
| `AskUserQuestion` | Confirmation gates + HUMAN-INPUT handling |
| `Agent` | Per-finding subagent dispatch (SUB-SKILL + PLAN-FIRST) |

**Deliberately omitted** from `allowed-tools`: `git commit`, `git push`, `git reset`, `rm`. The skill never commits, pushes, resets, or deletes outside its own ledger/subplan files.

---

## Output Format

Single resolution ledger at `.project/audits/<date>/audit-resolver-ledger.md` using `templates/output-template.md`. Optional companion artefacts:

- `.project/audits/<date>/audit-resolver-subplans/<id>-<slug>.md` — per-PLAN-FIRST finding
- `.project/audits/<date>/audit-resolver-reaudit-diff.md` — if `--reaudit` ran

The ledger is **the resume state**. Re-invoking audit-resolver picks up where it left off by reading prior ledger entries and skipping already-completed findings.

---

## Behavioural Rules

1. **Never commit.** Branch / commit / push are user decisions; the skill writes files only.
2. **Always confirm destructive ops.** File deletions, mass refactors, schema migrations require explicit `AskUserQuestion` approval.
3. **Verify after every batch.** Small, validated steps; no piling up un-verified changes.
4. **Halt on verifier failure.** Never proceed past a broken state without user direction.
5. **Respect severity flags.** Don't sneak warnings in when `--severity=critical` was set.
6. **Sub-skill dispatch where appropriate.** Use the right tool; don't reinvent.
7. **Ledger everything.** Every action + every skipped item with reason.
8. **Australian English.**

---

## Edge Cases

1. **No audit report found** — STOP with clear message and pointer to `/ai-utilities:plan-completion-audit`.
2. **0 findings** — Stop; report "nothing to do".
3. **Report from different repo** — Detect via referenced paths not existing; abort.
4. **Uncommitted changes** — Phase 4 stash flow; never silently overwrite.
5. **Mid-run interruption** — Ledger writes are append-only; resume skips completed findings.
6. **Verifier unavailable** (no `npm`, no `tsc`) — Mark findings "applied unverified"; user must verify manually.
7. **Sub-skill not installed** — Mark "deferred — install required plugin first"; do not attempt fix.
8. **Cyclic dependency in findings** — Surface as manual review item; don't auto-order.
9. **Web Lifter plugin marketplace itself** — `scripts/verify-stack.sh` detects via `scripts/check-versions.mjs` presence and uses that + `python tests/scripts/test_smoke.py` as the verifier.
10. **User says stop mid-batch** — Finish current edit safely; write ledger; exit cleanly.
11. **Malformed report structure** — Best-effort parse + warn user that some findings may be missed.
12. **Multiple audit reports in the folder** — Default to the newest by timestamp filename (this is now deterministic). Only pause to ask if the user passed `$ARGUMENTS` that are ambiguous or if filenames are non-standard and mtime ordering is unclear.
