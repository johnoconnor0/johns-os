# Workstream Clustering

How `triage.py compile` decides which issues belong in one sitting, what the
result can and cannot tell you, and where it will be wrong.

## The algorithm

Union-find over a two-tier signal graph.

**Hard edges — merge unconditionally.** A shared parent, or a parent/child
relation between the two issues. The tracker's own declared structure outranks
every heuristic here: splitting a parent issue from its sub-issues would be an
obviously wrong answer however the tokens score.

**Soft edges — merge above a threshold.**

```
score = 0.30 · same_initiative
      + 0.30 · path_affinity
      + 0.20 · jaccard(labels)
      + 0.15 · jaccard(tokens)
      + 0.05 · same_project

path_affinity = 1.0  share an exact file
                0.6  share a depth-2 directory prefix
                0.0  otherwise

MERGE_THRESHOLD = 0.34
```

`path_affinity` is deliberately not a Jaccard. Two issues sharing one file out of
ten are strongly related, and a set-overlap ratio would score that 0.1.

Depth-2 prefixes only. Depth 1 (`src`) merges the entire repository.

## The property that matters

**No single signal reaches 0.34. Two must agree before anything merges.**

That is the whole defence against one label collapsing a forty-issue backlog into
a single cluster. It is also the first thing a future tuner will destroy, because
raising any one weight past the threshold looks like a small change and silently
turns the clustering into single-signal grouping.

If you change the weights, re-check that `max(WEIGHTS.values()) < MERGE_THRESHOLD`
still holds. There is a test for it.

## Determinism, and the cost of the size cap

Without a size cap, transitive union-find chains A–B–C–…–Z into one "workstream"
whose ends share nothing. `MAX_WORKSTREAM_SIZE = 8` prevents that.

The cap makes the result **merge-order dependent**, which is why merges are
applied strongest-first, ordered by `(-score, id, id)`. That makes the output
reproducible — the same queue always produces the same grouping — without making
it globally optimal. When the cap bites, the strongest pairing is the one that
survives, and a weaker pairing that would have joined the same cluster becomes its
own workstream instead. That is a real limitation, not a rounding error.

## What this cannot see

**Tracker issues carry no file paths.** Locally-detected findings do — a detector
records what it looked at — but an issue pulled from Linear almost never will. So
path affinity, joint-strongest signal, is blind on exactly the items this feature
exists to handle.

The mitigation is `derived_paths`: extract path-shaped tokens from the issue body,
then **keep only those that exist on disk**. The verification is the point. Without
it this is a regex inventing file paths out of prose, and a parallel-safety verdict
computed from invented paths is worse than one computed from no paths at all.

Every workstream therefore reports `path_evidence`:

| value | meaning |
| --- | --- |
| `declared` | a detector recorded the path |
| `derived` | extracted from issue text and verified to exist |
| `none` | no path evidence at all |

and `path_evidence: none` forces `parallel_safe: false`. **Unknown is not safe.**

## Reading `parallel_safe`

It answers one question: could two workstreams be *written* at the same time
without touching the same files?

- It is **never** emitted without `parallel_safe_reason`. A bare boolean gate is
  one people override without reading.
- It does **not** gate the analysis fan-out. Those agents are read-only and cannot
  collide; gating analysis on it would halve the throughput. `triage.py
  dispatch-plan` reports it and ignores it, on purpose.
- Its real use is telling a human which workstreams could be split across separate
  sessions or git worktrees — the only genuinely parallel *write* path available.

## Titling

The parent issue's own title, when one member is the parent of the others.
Somebody already wrote a sentence describing exactly that group of work.

Failing that, tokens shared by at least half the members, or a shared label — both
marked `title_confidence: low`, because they produce serviceable-but-flat names.
That flag is the one place an LLM rename genuinely earns its cost, and the skill
offers it only there.

## Agent routing

An ordered, most-specific-first table matched against member paths, labels and
titles. First hit wins; `solution-architect` is the default. `agent_confidence` is
the fraction of members that matched, so a low value means the workstream is mixed
and the routing is a guess.

## Where it will be wrong

- A workstream spanning two genuinely unrelated concerns, because they shared an
  initiative and a label. The dispatched agent is told to say so.
- Two workstreams that should be one, because the size cap split them.
- `path_evidence: none` on most tracker-sourced issues, making almost everything
  look parallel-unsafe until someone adds paths.
- Routing to `solution-architect` when nothing matched, which reads as a decision
  and is actually an absence — check `agent_confidence: 0.0`.
