# Audit Resolution Ledger — {{audit_report_name}}

**Date started:** {{date_dd_mm_yyyy}}
**Date completed:** {{date_dd_mm_yyyy}}
**Original audit report:** `{{report_path}}`
**Plan audited:** `{{plan_path}}`

---

## Baseline

| Field | Value |
|-------|-------|
| Branch | `{{branch}}` |
| Baseline ref | `{{baseline_ref_short}}` ({{baseline_subject}}) |
| Working tree at start | clean / dirty (stashed as `{{stash_name}}`) |
| Verifier(s) detected | {{verifier_list}} |

---

## Findings Inventory (parsed from report)

| ID | Severity | Phase | File:Line | Category | Description |
|----|----------|-------|-----------|----------|-------------|
| F001 | {{severity}} | {{phase}} | {{file:line}} | {{category}} | {{description}} |

Totals — {{n}} findings total. CRITICAL: {{n}} | WARNING: {{n}} | SUGGESTION: {{n}}.

---

## Plan (triage from Phase 2)

| Order | ID | Strategy | Sub-skill (if applicable) | Depends on |
|-------|----|----------|---------------------------|------------|
| 1 | F00X | AUTO | — | — |
| 2 | F00Y | SUB-SKILL | `database-design:rls-policy-designer` | F00X |

Severity filter applied: `{{severity_filter}}`. Phase filter: `{{phase_filter}}`.

---

## Execution Log

| Order | ID | Strategy | Files touched | Verifier | Duration | Outcome |
|-------|----|----------|---------------|----------|----------|---------|
| 1 | F00X | AUTO | `path/a.ts`, `path/b.ts` | `npx tsc --noEmit` clean | 0:42 | ✓ closed |
| 2 | F00Y | SUB-SKILL | (deferred to sub-skill) | sub-skill reports OK | 1:18 | ✓ closed |
| 3 | F00Z | PLAN-FIRST | `path/c.ts`, `path/d.ts` | `npm test` 12/12 pass | 4:55 | ✓ closed |
| 4 | F00A | HUMAN-INPUT | — | — | — | user chose "defer" |

---

## Skipped / Deferred

| ID | Severity | Reason | Action required to resume |
|----|----------|--------|---------------------------|
| F00A | SUGGESTION | User chose defer | Re-invoke `/ai-utilities:audit-resolve --severity=suggestion` when ready |
| F00B | WARNING | Sub-skill `<plugin:skill>` not installed | `/plugin install <plugin>@web-lifter-plugins` then re-run |

---

## Re-audit Diff (if `--reaudit` ran)

| Status | Count | Notes |
|--------|-------|-------|
| Closed (in original, not in new) | {{n}} | |
| Unchanged (in both) | {{n}} | |
| New (regressions) | {{n}} | {{description if any}} |

Verdict delta:
- Phase 1 verdict: `{{old_verdict}}` → `{{new_verdict}}`
- Phase N verdict: `{{old_verdict}}` → `{{new_verdict}}`

---

## Final Diff (since baseline)

```
git diff --stat {{baseline_ref_short}}..HEAD

 N files changed, X insertions(+), Y deletions(-)
 ...
```

---

## Summary

- **Addressed:** {{n_addressed}} of {{n_total}} findings ({{pct}}%)
- **Skipped / deferred:** {{n_skipped}}
- **Failed (verifier breakage):** {{n_failed}}
- **Files touched:** {{n_files}}
- **Verifier final state:** clean / dirty
- **Total elapsed:** {{total_minutes}} min

### Suggested next step

{{one of:
- "Review the diff (`git diff {{baseline_ref}}..HEAD`) and commit when satisfied."
- "Re-run `/ai-utilities:plan-completion-audit` to confirm closure."
- "Address the {{n_skipped}} deferred items in a follow-up session."
- "Investigate the {{n_failed}} verifier failures above before committing."
}}
