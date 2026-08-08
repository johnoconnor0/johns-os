# Check Families

The audit runs the families that apply to the repository in front of it, decided by
the repository rather than by a fixed list. The registry is
`${CLAUDE_PLUGIN_ROOT}/scripts/families.py`; this document explains it.

## Why families replaced phases

The previous design ran eleven numbered phases and instructed the model to "execute
every phase in order... never skip a phase". Nine of the eleven assumed
Next.js/React/TypeScript/npm/Supabase. Phase 10 was entirely Supabase; Phase 11 was
frontend-to-backend alignment.

On a Python repository with no frontend and no database that produced two honest N/A
rows and nine phases of ceremony — and the single real run on record simply routed
around the instruction, which is the clearest available evidence that prose does not
hold this kind of line.

The same problem was solved once in this repo already: `create-data-model` assumed
Postgres on every project until dialect adapters replaced the assumption with a
lookup. This is that, applied to checks.

## Five outcomes

| Outcome | Means |
| --- | --- |
| `passed` | It ran, and found nothing |
| `failed` | It ran, and found something |
| `not-applicable` | It is not relevant to this repository. **Reason required** |
| `not-checked` | It is relevant, but could not run here. **Reason required** |
| `errored` | It tried to run and broke. **Reason required** |

The distinction between the middle two is the point. "This repository has no
database" and "the database client is not installed" produce identical silence
otherwise, and silence reads as a pass. `findings.py` enforces the required reason;
it is not a documentation convention.

## Two predicates per family

```python
applies_when(ctx) -> (relevant?, reason)   # No  -> not-applicable
requires(ctx)     -> (runnable?, reason)   # No  -> not-checked
```

Keeping them separate is what makes the two outcomes distinguishable. A runner never
decides either one, so the distinction cannot be quietly collapsed inside a check.

## The registry

| Family | Applies when | Can fail at |
| --- | --- | --- |
| `plan-inventory` | A plan was parsed | critical |
| `unfinished-markers` | Always | suggestion |
| `static-analysis` | The stack declares a lint or typecheck command | warning |
| `tests` | The stack declares a unit-test command | critical |
| `build` | The stack declares a build command | critical |
| `secrets` | Always | critical |
| `dependency-audit` | A package manager was detected, and its auditor is on PATH | critical |
| `repo-hygiene` | It is a git repository | warning |
| `dead-code` | Python sources were detected | suggestion |
| `data-layer` | A database or migration sources were detected | critical |
| `interface-alignment` | Both a frontend and a backend or database were detected | warning |
| `docs-references` | Markdown is present | warning |
| `plan-drift` | A plan was parsed | warning |

Three of these are **model-driven**: `plan-inventory`, `data-layer` and
`interface-alignment` need judgement the script cannot supply, so it reports them
`not-checked` with that as the reason and the skill fills them in. Being listed
explicitly is what stops them looking like a silent pass.

## Where the stack comes from

`stack_probe.py`, through a three-rung ladder, because this plugin and
`engineering-lifecycle` install separately and either can be present without the
other:

1. `.project/.engineering/context/stack.json`, written by the other plugin's
   SessionStart hook. Free and authoritative.
2. Its `stack_detection.py`, imported from a co-installed copy.
3. A small vendored probe covering only the markers these families gate on.

The answer records which rung produced it, so a wrong guess is visible in the report
rather than silently deciding which half of the audit ran.

Rungs 2 and 3, and the `docs-references` reference checker, look for
`engineering-lifecycle` in two places: as a sibling directory, which is how this
repository's own checkout is laid out, and under
`~/.claude/plugins/cache/<marketplace>/engineering-lifecycle/<version>/`, which is
how a real install is laid out. Only the first used to be tried, so on an installed
plugin the lookup resolved *inside* `ai-utilities` and skipped the version segment.
When neither resolves, the report names the paths it tried rather than asserting the
other plugin is not installed - which it cannot know.

## Adding a family

Append a `Family` to `REGISTRY` in `scripts/families.py` and a runner in
`scripts/checks.py`. Nothing else changes: the report is a fold over whatever ran,
and `test_every_registered_family_appears_in_output` will immediately require the
new one to appear with an explicit outcome.

That test is the replacement for "never skip a phase". A condition the run fails on,
rather than a sentence a model can route around.
