---
name: audit-resolve
description: Resolve / address / implement the action items from a plan-completion-audit report. Wraps the audit-resolver skill with a convenient slash invocation.
argument-hint: [report-path | flags]
---

# Audit Resolve

Convenience command for invoking the `audit-resolver` skill.

## Flow

The command is a thin pass-through. The `audit-resolver` skill owns **all** confirmation gates (Phase 3 plan approval + per-HUMAN-INPUT-finding pauses) so the user is asked exactly once, not twice.

1. **Welcome.** One-liner: "Dispatching to audit-resolver. The skill will discover the latest report under `.project/audits/`, show you the plan, and ask for confirmation before executing."
2. **Dispatch immediately** to the `audit-resolver` skill with `$ARGUMENTS` forwarded verbatim. Skill phases handle discovery (1), triage (2), confirmation (3), pre-flight (4), execution (5), optional re-audit (6), ledger (7).
3. **Report back** once the skill returns:
   - Path to the resolution ledger (`.project/audits/<date>/audit-resolver-ledger.md`)
   - Final diff hint (`git diff <baseline-ref>..HEAD --stat`)
   - Suggested next step (review the diff and commit when satisfied)

## Flags (forwarded verbatim to the skill)

- `--dry-run` — produce the action plan + diff preview without executing
- `--severity=critical[,warning,suggestion]` — restrict severity (default: all three)
- `--phase=N[,N,...]` — restrict to specific audit phases
- `--reaudit` — at the end, re-run plan-completion-audit and diff verdicts
- `--no-confirm` — skip per-batch confirmation (still pauses on HUMAN-INPUT items)
- `--ledger=<path>` — override ledger location

## Common usage

```
# Most common — fix everything from the latest audit, with per-batch confirmation
/ai-utilities:audit-resolve

# Preview the plan only
/ai-utilities:audit-resolve --dry-run

# Address only CRITICAL findings + re-audit when done
/ai-utilities:audit-resolve --severity=critical --reaudit

# Limit to specific phases (e.g. only Phase 1 + Phase 8 from the report)
/ai-utilities:audit-resolve --phase=1,8

# Point at a specific report (when multiple exist)
/ai-utilities:audit-resolve .project/audits/plan-completion-audit/2026-05-20_142530.md
```

## Behavioural Rules

1. **Never invokes git commit / push / reset.** User owns version control.
2. **Defers heavy work to the audit-resolver skill.** This command stays light.
3. **Surfaces the ledger path** in the final message so the user knows where to look.

## Error Handling

- **No audit report found** — STOP with: "Run `/ai-utilities:plan-completion-audit` first to generate a report, then re-invoke this command."
- **Multiple recent reports** — Ask via `AskUserQuestion` which one to action.
- **Skill not available** — STOP with: "audit-resolver skill missing. Reinstall the utilities plugin: `/plugin install utilities@web-lifter-plugins`."

## Final Message

After the skill completes, print:

> *Resolution complete. {{n_addressed}} of {{n_total}} findings addressed.*
> *Ledger: `.project/audits/<date>/audit-resolver-ledger.md`*
> *Diff: `git diff <baseline>..HEAD --stat`*
> *Next step: review the diff and commit when satisfied.*
