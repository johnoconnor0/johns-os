# Evaluation framework

This is the scoring engine for `skill-review`. It condenses a 34-section extension-review checklist into ten weighted dimensions tuned for Claude Code marketplaces, plugins, and skills. Score each dimension, weight it, sum to a 0–100 total, then apply hard-fail gates and verdict bands.

---

## Scoring scale (per dimension)

Score every dimension 0–5. Use whole numbers.

| Score | Meaning |
|---|---|
| 5 | Strong. Practice is explicit, correct, and least-privilege. No concerns. |
| 4 | Good. Minor gap that does not affect safety. |
| 3 | Adequate. A real but non-severe gap; fix recommended. |
| 2 | Weak. A gap that materially raises risk; fix required to approve. |
| 1 | Poor. A serious gap; likely blocks approval. |
| 0 | Failing. Dimension is absent or actively unsafe; blocks approval. |
| N/A | Genuinely not applicable to this artifact (e.g. network checks on a prose-only skill). Excluded from the weighted total — do not score 0 for N/A. |

---

## Dimensions and weights

Weights sum to 100. Weighted total = Σ (dimension_score / 5 × weight), computed only over applicable dimensions, then rescaled to 0–100 if any dimension is N/A.

| # | Dimension | Weight | Focus |
|---|---|---|---|
| 1 | Manifest & structure integrity | 8 | Valid `plugin.json` / `marketplace.json` / `SKILL.md` frontmatter; kebab-case names match dirs; semver; referenced component paths resolve; no placeholder text. |
| 2 | Provenance & supply chain | 12 | Known/verifiable publisher; pinned & lockfiled deps; no typosquats; reviewed lifecycle/install scripts; no unexpected binaries; mutable-vs-pinned source refs. |
| 3 | Permissions & least privilege | 14 | `allowed-tools` scoped to purpose; no unrestricted `Bash`; MCP/LSP scopes justified; no silent scope expansion on update; write/delete/admin separated from read. |
| 4 | Prompt & instruction integrity | 16 | No hidden/indirect instructions; nothing that overrides user intent, weakens controls, conceals actions, or fabricates success; injection resistance; untrusted content separated from trusted instructions. |
| 5 | Secrets & credential hygiene | 12 | No embedded secrets in code/prompts/examples/tests; secrets from a manager not the model; tool/log redaction; dev≠prod; not extractable via injection. |
| 6 | Tool-use & action safety | 12 | Read-only default; confirmation before send/publish/deploy/delete/pay; target/recipient verification; idempotency; undo/rollback; no silent scope expansion. |
| 7 | Data handling & privacy | 8 | Data classified & minimised; production data not required for eval; no exfiltration paths; training-use disabled where relevant; tenant/user isolation. |
| 8 | Network & external communication | 6 | Every endpoint necessary & ideally allowlisted; SSRF & internal-metadata protection; TLS validation; external responses treated as untrusted. |
| 9 | Reliability & correctness | 6 | Does the claimed task end-to-end; handles malformed/missing input & failed services; fails safe; retries don't duplicate destructive actions; no fabricated results. |
| 10 | Documentation, governance & lifecycle | 6 | Purpose + owner clear; docs match behaviour; logging/audit of consequential actions; approval recorded; version/change control; decommission/revocation path. |

**Why these weights:** prompt integrity, permissions, provenance, secrets, and action safety carry the most weight because they are where a malicious or careless Claude Code extension does real damage (data exfiltration, destructive actions, credential theft, behaviour hijacking). Structure, docs, and reliability matter but rarely cause a security incident on their own.

---

## Hard-fail gates (override the score → REJECT)

Evaluate these before trusting the number. Any single gate tripping forces **REJECT** even if the weighted score is high, because the score can be dragged up by strong performance elsewhere while one fatal issue remains.

| Gate | Trips when |
|---|---|
| G1 Live secret | A real/working credential, private key, or token appears in any file, prompt, example, or test fixture. |
| G2 Remote code execution | Code fetches then executes remote content (`curl … \| sh`, `wget … \| bash`, `eval`/`exec` of a network response, runtime install of an unpinned remote package, dynamic import from a URL). |
| G3 Deceptive/anti-safety instruction | A prompt/instruction tells the agent to hide actions from the user, disable or weaken safety/approval/permission controls, exfiltrate data, or claim success without verifying. |
| G4 Ungated destructive power | A destructive or external-effect action (delete, overwrite, deploy, send, publish, purchase, transfer) is reachable with no confirmation and no scope limit. |
| G5 Untrusted/mutable source | A dependency or listed plugin is known-malicious/typosquatted, or points to a mutable remote ref that can change executed behaviour with no version bump or re-review. |
| G6 Injection → action | Untrusted/retrieved content can trigger a real external action or tool call without user confirmation (indirect prompt injection reaches a sink). |

Record each gate as PASS / FAIL / N-A with evidence. Any FAIL is a CRITICAL finding.

---

## Finding contract

Emit every issue in this shape (aligns with the software-assurance finding contract):

```yaml
id: SR-001
dimension: 1-10 (name)
severity: CRITICAL | HIGH | MEDIUM | LOW | INFO
confidence: high | medium | low     # high = confirmed from file/scanner; low = inferred concern
title: short title
summary: concise, evidence-backed explanation
evidence:
  - type: file | scanner | manifest | frontmatter | mcp | user-input
    ref: path:line or scanner-rule-id
impact: what can go wrong
recommendation: the robust fix (scope the tool / pin the dep / add the gate)
verification: how to prove the fix landed
gate: G1..G6 | none      # set if this finding trips a hard-fail gate
```

Severity guidance: CRITICAL = trips a gate or enables data loss/exfiltration/credential theft/behaviour hijack. HIGH = materially unsafe, must fix before approval. MEDIUM = should fix. LOW = minor. INFO = note/observation.

---

## Verdict bands

Per artifact:

| Verdict | Condition |
|---|---|
| REJECT | Any hard-fail gate FAIL, OR any unresolved CRITICAL, OR weighted total < 50. |
| APPROVE WITH CONDITIONS | No CRITICAL; ≥ 1 HIGH/MEDIUM to fix; total 50–79. Conditions must be listed explicitly and be verifiable. |
| APPROVE | No CRITICAL/HIGH; total ≥ 80; all gates PASS. |

**Containers inherit the worst child verdict.** A marketplace is not APPROVE while any listed plugin is REJECT or unreviewed. A plugin is not APPROVE while any bundled skill is REJECT.

Residual MEDIUM/LOW findings on an APPROVE must still be listed and, ideally, formally accepted by the owner in the sign-off block.

---

## Applicability notes by artifact type

- **Prose-only skill** (no tools, no network, no scripts): dimensions 6, 8 often N/A; 3 reduces to "does it even need the tools it declares"; weight lands on 4 (prompt integrity), 2 (provenance), 5 (secrets), 10 (docs/governance).
- **Plugin**: score the plugin itself on all ten, then score each bundled skill/agent/hook and roll up.
- **Marketplace**: score the catalog on 1, 2, 5, 10 directly (manifest validity, source trust of listings, no leaked secrets, listing hygiene/ownership), then recurse into every listed plugin and inherit the worst verdict.
