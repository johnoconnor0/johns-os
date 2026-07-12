# Skill Review Report — <target name>

- **Reviewed path:** <path>
- **Scope:** <marketplace | plugin | skill | all>
- **Mode:** <static | full>
- **Reviewer:** skill-review (Claude Code) — automated readiness review, not a legal opinion or formal certification
- **Date:** <date>
- **Scanner:** scan_extension.py <version/date> — <ran | not run: reason>

---

## 1. Verdict summary

| Artifact | Type | Weighted score | Gates | Verdict |
|---|---|---|---|---|
| <name> | <M/P/S> | <n>/100 | <PASS/FAIL> | <APPROVE / APPROVE WITH CONDITIONS / REJECT> |

**Overall:** <verdict + one-line reason. Container inherits worst child verdict.>

---

## 2. Inventory (what was inspected)

| Artifact | Path | Declared tools | MCP servers | Hooks | Endpoints | Notes |
|---|---|---|---|---|---|---|
| <name> | <path> | <tools> | <servers> | <n> | <domains> | <remote-source? etc> |

---

## 3. Hard-fail gates

| Gate | Result | Evidence |
|---|---|---|
| G1 Live secret | PASS/FAIL/N-A | <path:line> |
| G2 Remote code execution | PASS/FAIL/N-A | <path:line> |
| G3 Deceptive/anti-safety instruction | PASS/FAIL/N-A | <path:line> |
| G4 Ungated destructive power | PASS/FAIL/N-A | <path:line> |
| G5 Untrusted/mutable source | PASS/FAIL/N-A | <path:line> |
| G6 Injection → action | PASS/FAIL/N-A | <path:line / test note> |

---

## 4. Scorecard (per artifact)

### <artifact name> — <score>/100 — <verdict>

| # | Dimension | Score /5 | Weight | Notes |
|---|---|---|---|---|
| 1 | Manifest & structure integrity | | 8 | |
| 2 | Provenance & supply chain | | 12 | |
| 3 | Permissions & least privilege | | 14 | |
| 4 | Prompt & instruction integrity | | 16 | |
| 5 | Secrets & credential hygiene | | 12 | |
| 6 | Tool-use & action safety | | 12 | |
| 7 | Data handling & privacy | | 8 | |
| 8 | Network & external communication | | 6 | |
| 9 | Reliability & correctness | | 6 | |
| 10 | Documentation, governance & lifecycle | | 6 | |

*(Repeat this block for every plugin and skill. N/A dimensions excluded from the weighted total.)*

---

## 5. Findings (by severity)

> Confirmed = read from file/scanner. Inferred = reasoned concern, not fully verified (see `confidence`).

```yaml
- id: SR-001
  dimension: <n (name)>
  severity: CRITICAL | HIGH | MEDIUM | LOW | INFO
  confidence: high | medium | low
  title: <short>
  summary: <evidence-backed>
  evidence:
    - type: file | scanner | manifest | frontmatter | mcp | user-input
      ref: <path:line | rule-id>
  impact: <what can go wrong>
  recommendation: <robust fix>
  verification: <how to prove fixed>
  gate: <G1..G6 | none>
```

*(List all findings, CRITICAL first.)*

---

## 6. Conditions to approve (if APPROVE WITH CONDITIONS)

1. <concrete, verifiable condition tied to a finding id>
2. …

---

## 7. Remediation roadmap

| Priority | Finding id | Action | Owner | Verification |
|---|---|---|---|---|
| P0 | SR-00x | | | |
| P1 | | | | |

---

## 8. Checks not performed / evidence unavailable

- <check> — <why not performed / what evidence was missing / what would be needed to confirm>

---

## 9. Sign-off

- **Residual risks accepted:** <list MEDIUM/LOW findings being accepted, or "none">
- **Approver:** ____________________  **Role:** ____________  **Date:** __________
- **Decision:** APPROVE / APPROVE WITH CONDITIONS / REJECT
- **Re-review due:** <date / trigger, e.g. next version bump or permission change>
