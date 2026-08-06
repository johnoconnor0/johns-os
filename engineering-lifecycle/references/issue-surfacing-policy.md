_What to surface when something in a project looks wrong, and what the system can and cannot make you do._

# Issue Surfacing Policy

## The honest framing

The request behind this was "force the AI to surface every time something happens
that shouldn't". That cannot be built. No hook can compel a tool call, and no
instruction reliably survives a long session.

So the design does the only three things that actually help, in descending order of
how much they depend on anyone's good intentions:

1. **Move work out of the model's hands.** Every anomaly a script can find is found
   by a script. The model's compliance stops being load-bearing for the mechanical
   half.
2. **Make the manual action one line with one required argument.** Cheap compliance
   is the only compliance there is.
3. **Make omission visible.** `detected` minus `queued` is computed and reported.
   The model cannot quietly skip a mechanical finding, because it never had to
   report it in the first place.

Step 4 — remind every turn — is the ceiling for the judgement half. Nothing stronger
exists.

## Surface this

- **Unexpected behaviour.** A command, hook or script that did something other than
  what its name and documentation say.
- **Contradictory state.** Two artefacts that disagree; a ledger entry with no
  source; a status that cannot be true.
- **Silent failure.** Something that returned success without doing the work. A
  verdict computed from nothing belongs here.
- **Dead references.** A document naming a file, skill, command or plugin that does
  not exist.
- **Degraded operation.** Works, but is slow, noisy, or produces output nobody can
  act on.
- **A workaround you had to invent.** If you had to route around something, the next
  person will too.

## Do not surface this

- Style preferences, or a refactor you would have done differently.
- Speculative problems with no evidence behind them.
- Anything already in the queue — check first; the id is content-derived, so a
  duplicate updates rather than duplicating, but a differently-worded duplicate does
  not.
- The absence of a feature nobody asked for.

## Severity

| Severity | Means |
| --- | --- |
| `critical` | Data loss, a credential exposed, or a verdict being asserted that was never computed |
| `high` | Something is wrong and will produce a wrong answer |
| `medium` | Something is wrong and produces noise, confusion, or wasted work |
| `low` | Worth knowing, not worth interrupting for |

The default filing threshold is `medium`. Items below it are still recorded and
still counted — `below_min_severity` is reported alongside the queue, so the two
numbers can be reconciled rather than quietly disagreeing.

## The command

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/surface-issue.py" record --title "<what is wrong>"
```

`--title` is the only required argument. Add `--severity`, `--path` (repeatable),
`--rule` and `--body` when they are known.

## What is deterministic, and what is not

**Structure is deterministic.** Schema violations, malformed JSON, orphaned
artefacts, contradictory ledger state, stale generated files, dead references,
directory drift — a script finds these, every time, without being asked.

**Meaning is not.** Whether a detected anomaly matters *here*. Whether a PRD and its
design document actually contradict each other. Whether something "isn't functioning
optimally". Whether a plan is internally consistent but solves the wrong problem.
These need judgement, and judgement is what step 4 above can only ask for.

Being clear about which half you are in is the point. A checker that guesses at the
second half produces noise, and noise gets ignored — the same lesson
`anti-slop-register.md` records.
