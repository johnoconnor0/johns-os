# Plan Completion Audit Report

## Summary

| Field | Value |
|-------|-------|
| **Project** | [project name] |
| **Date** | [YYYY-MM-DD] |
| **Plan Source** | [path to plan file] |
| **Overall Verdict** | **PASS** / **FAIL** / **PASS WITH WARNINGS** |
| **Tasks Complete** | X / Y (Z%) |
| **Critical Issues** | [count] |
| **Warnings** | [count] |
| **Suggestions** | [count] |

---

## Phase Results

### Phase 1: Plan Completion — [PASS / FAIL]

**Tasks checklist:**

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | [task from plan] | ✅ Complete / ⚠️ Partial / ❌ Missing | [details] |

**Unfinished work markers:** [count] TODO/FIXME/HACK found — see details below.

---

### Phase 2: Type Safety & Static Analysis — [PASS / FAIL]

**TypeScript:** [X errors, Y warnings]
**ESLint:** [X errors, Y warnings]
**Type escape hatches:** [X instances of @ts-ignore / as any]

---

### Phase 3: Bug & Logic Audit — [PASS / FAIL / WARNINGS]

| # | Severity | File:Line | Description |
|---|----------|-----------|-------------|
| 1 | CRITICAL / WARNING | `path/to/file.ts:42` | [description] |

**Test suite results:** [passed/failed/skipped]
**Dead code found:** [list or none]

---

### Phase 4: Code Structure & Optimisation — [PASS / WARNINGS]

**Architecture issues:** [list or none]
**God files (>500 lines):** [list or none]
**Circular dependencies:** [list or none]
**Performance concerns:** [list or none]

---

### Phase 5: Failsafes & Guardrails — [PASS / FAIL]

| Check | Status | Notes |
|-------|--------|-------|
| Input validation | ✅ / ❌ | |
| Error boundaries | ✅ / ❌ | |
| Loading states | ✅ / ❌ | |
| Empty states | ✅ / ❌ | |
| Error states | ✅ / ❌ | |
| Rate limiting | ✅ / ❌ / N/A | |
| Timeouts | ✅ / ❌ | |
| Environment guards | ✅ / ❌ | |

---

### Phase 6: Security — [PASS / FAIL / CRITICAL]

| # | Severity | Category | Details |
|---|----------|----------|---------|
| 1 | CRITICAL / WARNING | [secrets/injection/auth/etc] | [description] |

**Dependency vulnerabilities:** [critical/high/moderate counts]
**RLS coverage:** [all tables covered / gaps listed]

---

### Phase 7: Feature Hardening — [PASS / WARNINGS]

| Feature | Empty State | Loading | Error State | Edge Cases | Notes |
|---------|-------------|---------|-------------|------------|-------|
| [feature] | ✅ / ❌ | ✅ / ❌ | ✅ / ❌ | ✅ / ❌ | |

---

### Phase 8: Deprecated Cleanup — [PASS / FAIL]

**Orphaned files:** [count]
**Commented-out code blocks:** [count]
**Unused dependencies:** [list]
**Debug statements in production code:** [count]
**Stale migrations:** [list or none]

---

### Phase 9: Build Verification — [PASS / FAIL]

**Build command:** `[command]`
**Build result:** [success / failure]
**Errors:** [count]
**Warnings:** [count]
**Post-build type check:** [pass / fail]

---

### Phase 10: Supabase Backend Audit — [PASS / FAIL]

**10a. Schema:**

| Table | Columns | PK | FK | Indexes | RLS | Status |
|-------|---------|----|----|---------|-----|--------|
| [table] | [count] | ✅ | [refs] | [count] | ✅ / ❌ | OK / Issues |

**10b. RPC Functions:**

| Function | Params | Return | Security | Status |
|----------|--------|--------|----------|--------|
| [name] | [signature] | [type] | DEFINER/INVOKER | OK / Issues |

**10c. RLS Policies:**
[Summary of coverage — tables with/without policies, overly permissive policies]

**10d. Triggers & Realtime:**
[Trigger list, realtime publication status]

**10e. Storage & Edge Functions:**
[Bucket policies, edge function status, or N/A]

---

### Phase 11: Frontend ↔ Backend Alignment — [PASS / FAIL]

**Type alignment:**

| Area | Status | Details |
|------|--------|---------|
| Table types vs frontend interfaces | ✅ / ❌ | [mismatches] |
| RPC types vs call sites | ✅ / ❌ | [mismatches] |
| Enum values | ✅ / ❌ | [mismatches] |

**Query audit:**

| # | File:Line | Query | Issue |
|---|-----------|-------|-------|
| 1 | `path:line` | `.from('table').select(...)` | [missing column / wrong type / etc] |

**Missing backend objects:** [frontend references tables/functions that don't exist]
**Missing frontend consumers:** [backend objects with no frontend usage]
**Auth flow alignment:** [aligned / gaps]

---

## Prioritised Action List

### Critical (must fix before deploy)

1. [file:line] — [description]

### Warnings (should fix soon)

1. [file:line] — [description]

### Suggestions (nice to have)

1. [file:line] — [description]

---

*Audit performed by Claude Code using the plan-completion-audit skill.*
