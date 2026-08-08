# Changelog

## 0.3.0 - 2026-08-08

Seven defects recorded against `plan-completion-audit` after a single real run, which
produced a report that looked authoritative and was wrong. Read together they are one
failure mode: the audit lost information silently and then rendered a confident verdict
over the gap.

### Added

- **A markdown-table extractor, and parse coverage.** A plan stating fifteen work items
  in two tables parsed as six, because no extractor read tables and the only structure
  any of them could see was an unrelated six-step staging checklist — so the report
  announced "4 of 6 plan items complete (67%)" against a real denominator of
  twenty-one. Tables now compete in the tier that picks the finest reading of the
  declared structure. Separately, and more generally: every extractor now runs and its
  count is kept, the result names sections that state work but produced no items, and
  the renderer withholds the percentage when the extractor did not account for the
  plan. A partial parse was previously indistinguishable from a complete one.
- **A vocabulary for `findings[].status`.** `open`, `false-positive`, `accepted-risk`,
  `fixed`, with a `status_reason` required for anything that is not `open`. It was a
  free string that nothing validated and the renderer never read, so a run that
  examined six critical findings and dismissed all six rendered identically to one that
  had examined none — still six criticals in the header, and the work of checking them
  lost. Dismissed findings now leave the counts and appear in their own section.
- `render_report.py --check` validates a hand-edited `findings.json` without rendering.
- `scripts/eng-life.py`, which resolves `engineering-lifecycle` wherever it is
  installed rather than relying on a path only a source checkout has.

### Fixed

- **Child process output is decoded as UTF-8.** Three subprocess sites passed
  `text=True` with no `encoding=`, so on Windows output decoded as cp1252, which leaves
  0x90 undefined. The `UnicodeDecodeError` killed the reader thread `Popen.communicate`
  uses when `timeout=` is set; `is_alive()` was then false so no `TimeoutExpired` was
  raised, and `subprocess.run` returned `stdout=None` beside a returncode of 0. Every
  caller wrote `(proc.stdout or "")`, collapsing "printed nothing" into "we could not
  read it", and two families reported `passed` on evidence they never read.
- **The secrets scanner no longer fires on test literals.** Every finding in that
  family on the failing run was a false positive — six of its seven criticals, five of
  which said in the literal that they were not real. The path filter matched components
  of the *absolute* path, so a checkout under a directory named `tests` skipped the
  scan entirely while `api.leads.test.ts` in `api/src/` was treated as production
  source. Test-path matches are now down-weighted rather than dropped, and the loosest
  rule weighs an obvious-dummy denylist and Shannon entropy before raising.
- **`engineering-lifecycle` is resolved by install layout.** The probe used a sibling
  path that only resolves in a source checkout; installed, it pointed inside
  `ai-utilities` and skipped the version directory. `docs-references` therefore
  reported the plugin "not installed" on a machine with ten versions of it, and the
  `imported` rung of the stack ladder could never fire. A genuine absence now names the
  paths tried rather than asserting a fact it never checked.
- **`dead-code` reports `not-applicable` on a repository with no Python.** Its
  relevance gate admitted any Node tree while the runner implemented only Python, so a
  TypeScript repository got `not-checked` — "applies here but could not run" — for
  something that does not apply.
- **The `--stamp` write-back step was destructive as documented.** It said to re-run
  the audit and *then* hand-edit the results; the write truncates, so following that
  order destroys the assessment. The step is now edit-then-render, and `--stamp` is
  documented as what it is.
- `FamilyResult.validate` had never run outside the test suite, and `SEVERITIES` was
  never validated anywhere — an unknown severity sorted last through a fallback and
  vanished from the counts. Both are enforced now.
- `validation_errors` and the file-scope warning are rendered instead of being written
  to `findings.json` and never shown.

### Changed

- `--allow-untrusted-commands` is documented in `SKILL.md` and `check-families.md`,
  with the tradeoff, so the choice is made before the run rather than discovered in the
  output afterwards. **The gate itself is unchanged.** The report now says in one
  sentence when it contains no test, lint or build evidence; three scattered
  `not-checked` rows did not add up to that for a reader skimming a verdict table.
- `ordered-list` no longer matches inside fenced code blocks, where a worked example
  was eligible to become the inventory.

## 0.2.1 - 2026-08-07

### Fixed

- **The shell hooks died on any input they could not read.** All three `jq`-using hooks open with `set -euo pipefail` and then assign from a pipeline. When `jq` cannot parse stdin it exits non-zero, `set -e` treats that as fatal, and the script dies before reaching any of its graceful `exit 0` paths — so a payload the hook could neither read nor act on produced an uncontrolled non-zero exit with no message anywhere. `pre-write-skill.sh` is a PreToolUse gate whose own comment promises "if not, allow the write (graceful degradation)"; the parse path defeated the degradation the file documents. Each extraction now falls to `exit 0`.
- **Two hooks had never worked on macOS.** They lowercased with `${FILE_PATH,,}`, a bash 4 expansion. macOS ships bash 3.2, where that is not a silent mismatch but a hard `bad substitution` parse error, so both failed on every invocation. Lowercasing goes through `tr` instead; the case-insensitive match is unchanged.

Both were invisible until now because these hooks short-circuit at `command -v jq` — on a machine without `jq` they exit 0 having done nothing, so the real path had never executed locally. A new hook suite plus a macOS CI leg found them on the first run.

## 0.2.0 - 2026-08-06

### Changed

- **`plan-completion-audit` derives its checks from the plan and the stack instead of running a fixed list.** It ran eleven numbered phases and instructed the model to "execute every phase in order... never skip a phase", nine of which assumed Next.js/React/TypeScript/npm/Supabase. On a Python repository with no frontend and no database that produced two honest N/A rows and nine phases of ceremony — and the one real run on record simply routed around the instruction, which is the clearest evidence available that prose does not hold this kind of line. Thirteen check families now each answer two questions separately: is this relevant *here*, and can it actually run. Five outcomes replace pass/fail: `passed`, `failed`, `not-applicable`, `not-checked`, `errored`, and the last three **require** a reason. "This repo has no database" and "the database client is not installed" produce identical silence otherwise, and silence reads as a pass.
- **The plan is parsed by a cascade, not one pattern.** Checklists win outright; heading extractors compete on count, because the only real plan on record stated its nineteen items as numbered headings and a checkbox-only parser would have found zero and audited nothing, confidently. When nothing matches, the audit stops and asks rather than inventing an inventory.
- **The two skills exchange `findings.json`, not markdown.** `parse-audit-report.sh` described itself as "heuristic, not a strict parser" and asked its caller to sanity-check its own output count. Legacy reports still load, converted to the same shape and stamped `source: "markdown-fallback"` with a count of the rows it could not convert.
- **`audit-resolver` reports what the audit did not cover.** Closing every finding while three families never ran does not mean the repository is clean; `families_not_run` is surfaced before anything else, with `not-applicable` distinguished from `not-checked`.
- Findings carry two hashes doing two jobs: `identity` excludes the line number so a finding that moved matches its existing issue, and `content_hash` includes it so the issue gets updated. One hash over both would create a duplicate every time someone added an import.

### Fixed

- **Removed routing to four plugins and two agents that this marketplace does not ship**, and to a marketplace that is not the one in use. The delegation map now names only real agents and skills, and availability is probed at run time rather than assumed.
- **Resolved the skill's contradiction about its own output path.** The header directive and the body disagreed; both real runs on disk had followed the header, so that is now the only path stated.
- `verify-stack.sh` probed for two files belonging to a different repository and never knew about this one's single validation entrypoint. Replaced by `scripts/verify.py`, which asks — a repo-wide entrypoint, then the stack's declared commands, then file presence — and reports `unverified` rather than `passed` when nothing is found. The bash version exited 0 there, which reads as a pass to anything checking the exit code.
- Every skill now carries the four sections the plugin validator requires. None of them did, because no validator had ever been pointed at this plugin.
- The plugin has tests, and `scripts/validate-repo.py` discovers them rather than naming two directories explicitly.
- Both eval suites replaced. The audit's functional case still carried `<replace-with-real-path-to-project-root-or-plan-file>` and had never been runnable; the resolver's canonical activation case was "Read this for me".
- The audit example was an eleven-phase Supabase report copied from another marketplace; it is now generated by a real run against a committed fixture.

### Removed

- All six shell scripts and the fixed eleven-phase report template. `check-todos.sh` hardcoded ten file extensions, so a Go or Rust repo scanned clean by construction; `check-types.sh` reimplemented, worse, what stack detection already does; `check-unused-deps.sh` tested for orphans with `grep -rl "$BASENAME"`, which false-positives on any ordinary filename; `audit-supabase.sh` was the last hardcoded engine.
- `parse-audit-report.sh` and `verify-stack.sh`.

## Unreleased

### Added

- Public website metadata and repository-level quality/release documentation.

## 0.1.0 - 2026-07-12

### Added
- Initial release of the consolidated `ai-utilities` plugin for the johns-os marketplace,
  merging two former plugins into a single namespace:
  - `skill-creator` and `skill-review` (from the former `skill-ops` plugin, v2.1.1).
  - `plan-completion-audit` and `audit-resolver` plus the `audit-resolve` command (from the
    former `plan-review` plugin, v2.2.2).
- Merged hook wiring: a SessionStart welcome, a PreToolUse skill-content guard, and PostToolUse
  skill/script quality checks.

### Changed
- Namespaced all command references to `ai-utilities` (e.g. `/ai-utilities:audit-resolve`,
  `/ai-utilities:plan-completion-audit`).
- Repointed `skill-review` delegation from the non-existent `skill-evaluator` to the bundled
  `skill-review` skill.
- Repository/homepage metadata repointed to the johns-os marketplace.
