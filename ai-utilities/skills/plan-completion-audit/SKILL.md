---
name: plan-completion-audit
description: Audit a plan against what was actually built - deriving the checks from the plan and the detected stack, never from a fixed list.
argument-hint: [path-to-project-root-or-plan-file]
allowed-tools: Read Grep Glob Write Edit Bash(python:*) Bash(python3:*) Bash(git:*) AskUserQuestion
effort: high
---

# Plan Completion Audit

<!-- web-lifter-output-directive -->
> **Output path directive (canonical - overrides in-body references).**
> Each run writes ONE directory:
> `.project/audits/plan-completion-audit/<TIMESTAMP>/`, where `<TIMESTAMP>` is
> `YYYY-MM-DD_HHMMSS`, containing `findings.json` and `report.md`.
> `run-audit.py` creates it; do not invent a different path.
> One run = one new directory. NEVER overwrite a prior run. The timestamp is how
> `[[audit-resolver]]` discovers the latest report, and it still sorts
> chronologically now that it names a directory.
> Do NOT write to the project root or to bare filenames at cwd.

## Trigger

Use when the user asks whether a plan was actually implemented, wants a completion
audit, or asks what is left before shipping.

## When To Use

- After implementation work, to establish what was built against what was planned.
- Before a release, to get a defensible list of what is outstanding.
- When a plan and a codebase have drifted and nobody is sure which is right.

Do **not** use it as a general code review with no plan. It will tell you so.

## What this skill will not do

It will not run eleven fixed phases. The version this replaces did, nine of them
assuming Next.js and Supabase, and on a Python repository that produced nine
sections of ceremony around two real findings. Checks are chosen from the plan and
the detected stack. A check that does not apply says so, with the reason.

It will not report a percentage it did not compute. "0 of 19 complete" when nothing
assessed completion is not a measurement, it is the absence of one, and the report
distinguishes the two.

## Workflow

### 1. Run the deterministic half

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/run-audit.py" --root . --plan <path-to-plan>
```

Omit `--plan` to let it discover one. It prints the path of the `findings.json` it
wrote. This one command does everything mechanical: resolves the stack, parses the
plan into an inventory, decides which families apply, runs those that can run, and
records an explicit outcome plus a reason for every family in the registry.

**If it reports that no plan could be parsed, stop and ask the user for one.** An
audit with no inventory is a code review wearing a verdict, which is worse than no
audit. Do not proceed on a discovered README.

#### Decide about `--allow-untrusted-commands` before you run, not after

When the audited repository declares its own commands in
`.project/.engineering/context/stack.json`, `static-analysis`, `tests` and `build`
report `not-checked` and name the strings they refused to run. That refusal is
deliberate: executing command strings a repository hands you is how an audit becomes
an attack, and a JSON file that looks inert gets to name the executable and its
arguments.

The consequence is that the default run produces **no test, lint or build evidence**,
and a completion audit with no test evidence cannot say whether any of it works. The
flag only appeared in the output, after the run, so the choice was discovered rather
than made:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/run-audit.py" --root . --plan <path> --allow-untrusted-commands
```

Read the commands first — they are quoted verbatim in each family's `reason` — and
pass the flag only on a repository whose `stack.json` you are willing to execute.

`--timeout` sets how long one check command may take, in seconds, default 300. Raise
it when a suite is legitimately slower than that: a command that overruns is reported
`errored`, which is honest but is not the same as a failure, and on a repository whose
tests take eight minutes every run would say so.
Commands the probe *derived* from file presence are trusted without it, so this
matters only when `stack.detector` is `workspace`. The report states plainly at the
top when it contains no test evidence; do not present such a run as a verdict on
whether the work functions.

### 2. Read `findings.json`

Everything below works from that file. Note in particular:

- `plan_items[]` - the inventory, each with `status` and `mentions`.
- `families[]` - every registered family with `outcome` and `reason`.
- `findings[]` - what the mechanical checks found, with `identity` and `route`.
- `plan.coverage` - how much of the plan the extractor accounted for.
  `confident: false` means sections stating work produced no items, they are named in
  `unparsed_sections`, and no completion percentage will be reported. Check whether
  the plan is written in a form no extractor read before trusting the inventory.
- `stack.detector` - which rung answered. If it is `vendored`, the detection is a
  fallback and worth a sanity check before trusting the gating.

### 3. Assess the model-driven families

Three families are reported `not-checked` because they need judgement a script
cannot supply. Doing this work is the substance of the audit.

**`plan-inventory`** - for each entry in `plan_items[]`, read the code and assign:

| Status | Means |
| --- | --- |
| `complete` | Implemented and it matches what the plan asked for |
| `partial` | Exists but stubbed, incomplete, or missing described behaviour |
| `not-started` | No implementation anywhere |
| `deviates` | Implemented differently - say how, and whether the deviation is sound |
| `unverifiable` | Names something that does not resolve. Set by `plan-drift`; do not overwrite it with a guess |

Read the code. A file with a placeholder return or an empty body is `partial`, not
`complete`. Existence of a filename proves nothing.

**`data-layer`** - only when it applies. Use the detected dialect, not Postgres by
default: `engineering-lifecycle/references/` and `postgres-audit-guide.md` cover the
Postgres case, and on MySQL there is no row level security to warn about, and on
SQLite the database is a file.

**`interface-alignment`** - only when both sides were detected. Every call the
frontend makes must name something the backend actually exposes, and vice versa.

Also assess what the mechanical checks raised. A finding you have examined and judged
needs no action gets a `status` and a `status_reason` in `findings[]`:

| `status` | Means |
| --- | --- |
| `open` | Real, outstanding. The default |
| `false-positive` | The check matched something that is not the thing it detects |
| `accepted-risk` | Real, and a deliberate decision not to act |
| `fixed` | Already addressed since the scan ran |

Anything other than `open` **must** carry a `status_reason`; validation rejects it
otherwise, for the same reason a `not-applicable` family must say why. Dismissed
findings leave the severity counts and the prioritised actions and appear in their own
section with the reason, so the work of checking them is visible instead of lost.

### 4. Record what you assessed

Edit `findings.json` in place, then re-render. Two commands, in this order:

1. Write your conclusions into the file: `plan_items[].status` and `.reason`, the
   `plan-inventory` family `outcome`, and `findings[].status` / `.status_reason`.
2. Re-render:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py" <dir>/findings.json --out <dir>/report.md
```

The rendered report is a fold over what ran. There is no template to fill in.

**Do not re-run `run-audit.py` to save your assessment.** It regenerates
`findings.json` from scratch and the write truncates, so a re-run after editing
destroys exactly the work you meant to keep. This step used to say to re-run with
`--stamp` and *then* hand-edit; that ordering only ever worked one way round and
nothing enforced it.

`--stamp` overrides the run id so a second run reuses one output directory instead of
creating a sibling. It is for tests and for resuming a run that was interrupted before
any assessment existed - its own `--help` says "For tests." It is not part of this
step.

To check a hand-edited file against the vocabularies without rendering:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py" <dir>/findings.json --check
```

It exits non-zero and names each problem. A normal render also validates: it still
writes the report, but exits non-zero and the report says at the top that the document
did not validate.

### 5. File the findings, if a tracker is configured

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/eng-life.py" tracker plan
```

That shim resolves `engineering-lifecycle` wherever it is installed. The path this
step used to name, `${CLAUDE_PLUGIN_ROOT}/../engineering-lifecycle/bin/eng-life`,
only exists in a source checkout - installed plugins live in separate versioned
cache directories, so it resolved to a path inside `ai-utilities`.

When no tracker is configured this reports `configured: false` and the audit is
complete without it. Exit 3 means `engineering-lifecycle` itself could not be found,
and the message names the paths tried; the two are different outcomes. Findings carry a stable `identity` that excludes the line
number, so re-running the audit after unrelated edits matches existing issues
instead of creating duplicates.

## Inputs Inspected

- The plan named in `$ARGUMENTS`, or discovered under the repository.
- `.project/.engineering/context/stack.json` when it exists.
- The source tree, as git tracks it - so the project's own `.gitignore` decides
  what is in scope.

## Outputs

- `.project/audits/plan-completion-audit/<TIMESTAMP>/findings.json`
- `.project/audits/plan-completion-audit/<TIMESTAMP>/report.md`

## Safety Constraints

- **Do not fix anything.** This produces a report. `[[audit-resolver]]` applies fixes,
  behind its own confirmation gates.
- **Do not mark a family passed that did not run.** The five outcomes exist so that
  never has to happen; `findings.py` rejects a document that tries.
- **Do not invent a plan inventory.** If no plan parsed, stop and ask.
- **Do not report a completion percentage you did not establish.** Nor one over an
  inventory the extractor did not fully account for - check `plan.coverage.confident`.
- **Do not dismiss a finding without a `status_reason`.** Validation rejects it, for
  the same reason a `not-applicable` family must say why.
- **Do not re-run `run-audit.py` after recording an assessment.** The write truncates,
  so it destroys the assessment.
- Absence of code for a planned feature is a finding, not a pass.

## Reference

- [`references/check-families.md`](references/check-families.md) - the registry, the
  two predicates, and how to add a family.
- [`references/postgres-audit-guide.md`](references/postgres-audit-guide.md) - the
  Postgres/Supabase specifics, loaded only when that is the detected dialect.

After the report is written, tell the user:

> To action the findings, run `/ai-utilities:audit-resolve`. It reads `findings.json`
> directly, triages every finding, confirms with you, then applies fixes in verified
> batches.
