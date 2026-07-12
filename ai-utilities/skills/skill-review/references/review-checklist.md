# Review checklist (distilled)

The concrete checks behind each scoring dimension. Distilled from a 34-section extension-review checklist down to what matters for Claude Code marketplaces, plugins, and skills. Tags: **[M]** marketplace, **[P]** plugin, **[S]** skill. Untagged = all.

Score the dimension in `evaluation-framework.md` from how these checks land. Cite `path:line` evidence for anything you flag.

---

## 1. Manifest & structure integrity  [weight 8]

- Frontmatter/manifest parses: `SKILL.md` YAML valid; `.claude-plugin/plugin.json` and `marketplace.json` valid JSON. **[all]**
- Names are kebab-case and the frontmatter/manifest `name` matches its directory. **[P][S]**
- Plugin `version` is semver; marketplace entries have identifiable versions. **[M][P]**
- Every component path the manifest references (`skills`, `agents`, `hooks`, `commands`, `mcpServers`, `lspServers`) actually exists. **[P]**
- `description` is specific enough to route/trigger correctly and matches real behaviour. **[S]**
- No placeholder text (`TODO`, `<replace…>`), no orphaned/unreferenced files, no `.git`/`node_modules`/`__pycache__` bundled. **[all]**
- The exact reviewed version is identifiable and pinned (you know what you're approving). **[all]**

## 2. Provenance & supply chain  [weight 12]

- Publisher/maintainer is identifiable and reputable; ownership history has no unexplained handoffs. **[all]**
- Every plugin listed in the marketplace resolves to a source you can review; flag mutable remote refs (branch, `latest`, unpinned) that can change behaviour silently. **[M]**
- Dependencies inventoried (direct + transitive); versions pinned with a lockfile; no typosquatted or abandoned packages. **[P][S]**
- Install/lifecycle scripts reviewed; no unexpected binary downloads or compiled blobs. **[P][S]**
- No known-vulnerable/malicious/compromised dependencies. **[P][S]**
- Third-party or generated code identified; licences reviewed; nothing copied/unlicensed. **[all]**

## 3. Permissions & least privilege  [weight 14]

- `allowed-tools` is scoped to what the artifact actually does — flag anything broader than its stated purpose. **[P][S]**
- No unrestricted `Bash` where scoped `Bash(cmd:*)` would do; no wildcard tool grants without justification. **[P][S]**
- MCP servers and their scopes are each mapped to a real need; no unnecessary always-on/mutating servers. **[P]**
- Read vs write vs delete vs admin capabilities are separated, not bundled. **[all]**
- Permissions don't silently expand on update; material permission changes require re-approval. **[all]**
- Credentials/scopes are specific to the extension, not shared broad tokens; access can be revoked promptly. **[all]**

## 4. Prompt & instruction integrity  [weight 16]

- Read **all** instruction surfaces: `SKILL.md` body, agent prompts, hook scripts, command files, references loaded at runtime. **[all]**
- No hidden or indirect instructions loaded from files/URLs that change behaviour without a version bump. **[all]**
- Nothing that overrides user intent, weakens security/approval controls, or requests excessive access. **[all]**
- Nothing that conceals actions from the user, fabricates results, or claims success without verification. **[all]**
- Skill distinguishes fact from inference, handles ambiguity safely, and asks for clarification when needed. **[S]**
- Untrusted content (files, web, tool output, retrieved docs) is clearly separated from trusted instructions and cannot silently redefine tool behaviour. **[all]**
- **Injection tests (full mode):** direct injection, indirect injection from documents/webpages, instruction/system-prompt extraction, tool-output manipulation, encoded/obfuscated/multilingual payloads, attempts to bypass approval or conceal actions.

## 5. Secrets & credential hygiene  [weight 12]

- Scan code, prompts, examples, tests, docs for embedded secrets/keys/tokens/private keys. **[all]**
- Secrets come from an approved manager/env, never hardcoded, never written into prompts unless strictly required. **[P][S]**
- Tool outputs and logs redact credentials; sensitive fields can be masked. **[P]**
- Dev and prod credentials separated; test fixtures contain no real secrets. **[all]**
- Credentials can't be extracted via prompt injection; the extension can't enumerate unrelated secrets. **[all]**

## 6. Tool-use & action safety  [weight 12]

- Enumerate every action; classify read-only / reversible / destructive / privileged / external. **[P][S]**
- Read-only is the default; consequential actions require explicit confirmation. **[P][S]**
- Confirmation gates before: sending comms, publishing, purchases/financial transactions, deleting/overwriting, production deployment. **[P][S]**
- Recipient/target verification: right account, file, repo, branch, environment, recipient; don't infer identity from a first name; show the final target list before submit. **[P][S]**
- Retry logic can't duplicate actions; undo/rollback exists where possible; authoriser of each consequential action is recorded. **[P]**
- Actions stay within the user's stated scope; no silent expansion. **[all]**

## 7. Data handling & privacy  [weight 8]

- Identify data the artifact receives and data it can retrieve on its own; classify PII/confidential/financial/health/regulated/IP. **[all]**
- Data minimisation and purpose limitation; production data not required for evaluation (test data works). **[P][S]**
- No exfiltration paths; sensitive data not placed in URLs/query strings; outputs don't leak hidden metadata. **[all]**
- Model-training use of data disabled where relevant; tenant/user isolation holds (no cross-user/cross-tenant leakage). **[P]**
- Derived data (embeddings, summaries, logs, caches) accounted for and cleanable. **[P]**

## 8. Network & external communication  [weight 6]

- List all domains/endpoints contacted; confirm each is necessary; allowlist where practical. **[P][S]**
- No arbitrary-URL fetch → SSRF; internal network and cloud metadata endpoints blocked; redirects validated; TLS cert validation enforced. **[P]**
- No undeclared telemetry/tracking; outbound request contents reviewed. **[P][S]**
- External responses treated as untrusted content, not instructions; network failures fail safe. **[all]**

## 9. Reliability & correctness  [weight 6]

- The artifact actually performs its claimed task end-to-end (not just plausibly worded). **[all]**
- Handles malformed/incomplete input, missing files/records/credentials, unavailable services, timeouts, rate limits. **[P][S]**
- Fails safe; retries/backoff don't repeat destructive actions; state stays consistent after interruption. **[P]**
- No fabricated citations, files, actions, or results; uncertainty is communicated. **[all]**

## 10. Documentation, governance & lifecycle  [weight 6]

- Clear purpose, intended users, and out-of-scope statement; a named owner responsible for the capability. **[all]**
- Docs (install, usage, inputs/outputs, limitations, permissions, rollback) exist and match actual behaviour. **[P][S]**
- Consequential actions and tool calls are logged with identity/timestamp/target; logs redact PII/secrets. **[P]**
- Version/change control: material updates re-reviewed; permission/network/prompt/dependency diffs checked; rollback package kept. **[all]**
- Decommission path: revoke OAuth/keys/tokens, remove permissions/webhooks/jobs, delete stored data, confirm loss of access. **[P]**
- Approval decision and residual-risk acceptance are recorded before production use. **[all]**

---

## Final approval questions (fold into the sign-off)

- Is it necessary and beneficial? Is the source trustworthy? Is the exact version identifiable?
- Are instructions and code understandable? Are all requested permissions necessary?
- Is sensitive data protected? Are external systems/subprocessors known? Are consequential actions controlled?
- Has prompt-injection resistance been tested? Have security and reliability checks passed?
- Are ownership, monitoring, and incident/decommission processes established?
- Can it be disabled and removed cleanly? Are residual risks documented and formally accepted? Is approval recorded?
