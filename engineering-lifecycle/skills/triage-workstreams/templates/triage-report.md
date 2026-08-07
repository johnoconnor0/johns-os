---
initiative_id: <initiative-id>
skill: triage-workstreams
created_at: <iso-timestamp>
status: draft
confidence: medium
source_artifacts:
  - .project/.engineering/tracker/workstreams.json
---

# Triage Report

## Scope

<How many open items were pulled, from which tracker and which scope, and when.
Say plainly if the fetch was truncated or if any workstream was left ungrouped.>

## Workstreams

<One section per workstream. Keep the ids — they are what the dispatch plan and
the analysis files key on.>

### <ws-01-slug> — <title>

- **Issues:** <identifiers>
- **Severity:** <worst severity in the group>
- **Why these are one workstream:** <the signals that merged them. If the
  grouping looks wrong, say so here rather than working around it — the
  clustering is a heuristic and a wrong cluster is worth reporting.>
- **Agent:** <which agent analysed it>
- **Parallel safe:** <yes/no, and the reason the plan gave>

**Root cause**

<From the agent's analysis.>

**Proposed sequence**

1. <step>

**Risks and rollback**

<What could go wrong, and how to undo it.>

**Open questions**

<What the agent could not determine by reading. These belong in the questions
store, not only here.>

## Ordering

<Which workstreams can proceed now, which are blocked, and on what. Name the
dependency rather than implying it.>

## Not Covered

<Issues that were pulled but not grouped, workstreams deliberately deferred, and
anything the fetch could not see. An omission nobody wrote down reads later as
completed work.>
