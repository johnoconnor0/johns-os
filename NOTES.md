# New Engineering Plugin Plan

## Summary recommendation

Build a **new, smaller Claude Code engineering plugin** rather than trying to clean up the existing `engineering-os` in place.

The current `anthril-os` repo already has a strong conceptual direction, but it appears to have become too broad for day-to-day use. The existing `engineering-os` describes itself as a single plugin covering the full software engineering lifecycle, with product, architecture, application, database, data, AI, design, quality, security, DevOps, SRE, platform, docs, TPM, GRC, and shared engineering context. It also reports a very large surface area: **181 skills** and **127 specialist agents**.

That scale explains your issue: most skills will not trigger often, and the cognitive surface area is too large. Claude’s own skill documentation notes that skill descriptions are loaded into context for matching, but when there are many skills, descriptions may be shortened or dropped to fit the skill listing budget. ([Claude][1])

So the new plugin should be:

> **Lifecycle-first, not department-first. Small number of high-value skills. Agents for specialist judgement. Hooks for deterministic hygiene. Templates for repeatability. Scripts for validation. Council only where debate actually improves outcomes.**

I would call it something like:

```text
engineering-product-os
```

or:

```text
dev-lifecycle-os
```

My preferred name:

```text
engineering-lifecycle
```

It is clear, narrow, and describes the product: a plugin that helps you move from discovery → requirements → UX → architecture → data model → development → testing → release → maintenance.

---

# 1. Research findings from the Claude / Anthropic docs

## 1.1 Plugins are the right container

Claude Code plugins are specifically designed to package **skills, agents, hooks, MCP servers, LSP servers, monitors, scripts, and settings** as reusable extensions. Anthropic describes plugins as self-contained directories that extend Claude Code with custom functionality. ([Claude][2])

This matches your goal better than standalone skills because you want:

* Skills
* Agents
* Hooks
* Templates
* Output examples
* Reference docs
* Scripts
* Repo hygiene automation
* Potential LLM council orchestration

A single skill would be too limited. A plugin is the correct unit.

## 1.2 Use the official plugin directory layout

The docs are clear that `.claude-plugin/plugin.json` belongs inside `.claude-plugin/`, while `skills/`, `agents/`, `hooks/`, `.mcp.json`, `.lsp.json`, `monitors/`, `bin/`, `scripts/`, and `settings.json` belong at the plugin root. ([Claude][2])

Target structure:

```text
engineering-lifecycle/
  .claude-plugin/
    plugin.json

  skills/
  agents/
  hooks/
  scripts/
  templates/
  references/
  examples/
  schemas/
  evals/
  bin/
  monitors/
  .mcp.json
  .lsp.json
  settings.json
  README.md
  CHANGELOG.md
  LICENSE
```

## 1.3 Skills should be few, clear, and triggerable

Skills are directories containing `SKILL.md`, and the skill description is what Claude uses to decide when to invoke the skill. ([Claude][1]) ([Claude][1])

AgentSkills also emphasises that skill descriptions carry the “entire burden of triggering,” because agents initially load only the name and description before deciding whether to read the full skill. ([Agent Skills][3])

This strongly suggests the new plugin should **not** have 100+ skills. It should probably start with **12 to 18 core skills**.

## 1.4 Agents should be specialists, not duplicates of skills

Subagents are specialised assistants with their own context window, system prompt, and tool permissions. They are useful when a side task would otherwise flood the main conversation with file contents, logs, or search results. ([Claude][4])

So agents should not be “another way to run the same workflow.” They should be used for specialist analysis:

* architecture review
* security threat modelling
* database modelling
* test strategy
* delivery planning
* codebase profiling
* implementation planning
* LLM/AI evaluation

## 1.5 Hooks are perfect for repo hygiene automation

Hooks give deterministic control over Claude Code behaviour and can run shell commands when Claude edits files, finishes tasks, needs input, or uses tools. Anthropic describes hooks as a way to ensure actions always happen rather than relying on the LLM to remember. ([Claude][5])

This fits your repo hygiene examples exactly:

* update `.gitignore`
* update `.env.example`
* detect new secrets
* validate generated artefacts
* check architecture docs were updated
* update changelog reminders
* enforce test/runbook paths
* block dangerous Bash commands

Claude’s hook docs also distinguish **SessionStart** and **Stop**. `SessionStart` runs when Claude starts or resumes a session, and should stay fast. `Stop` runs when the main agent finishes responding and can inspect the last assistant message. ([Claude][6]) ([Claude][6])

## 1.6 LLM council is useful, but should be optional

Agent teams are useful when parallel exploration adds real value: research and review, competing hypotheses, cross-layer work, and independent feature modules. But they also add coordination overhead and token cost. ([Claude][7])

Your uploaded LLM Council design is well aligned with this. It proposes role-specialised advisors — Contrarian, First-Principles Thinker, Expansionist, Outsider, Executor, and Chairperson — with anonymised drafts, blind peer review, chair synthesis, observability events, quorum handling, and deterministic record/replay fixtures. 

My recommendation: include the council, but do **not** make it the default path for every task. Use it for high-stakes decisions:

* major architecture decisions
* build vs buy decisions
* risky implementation plans
* scaling strategy
* security-sensitive design
* product roadmap trade-offs
* migration plans
* AI system design

---

# 2. What is wrong with the current `anthril-os` direction?

I do **not** think the current work is useless. There are several strong ideas worth salvaging.

The existing plugin already has:

* a single-plugin structure
* shared scripts
* a project-local workspace contract
* a tracker / ledger concept
* hooks
* schemas
* handoffs
* lifecycle domains
* validation scripts
* action-item tracking

The `engineering-os` README says it consolidated many engineering domains into one plugin and stores generated work under a project-local `.anthril/.eng-os/` workspace.

The conventions file defines a useful workspace contract:

```text
.anthril/.eng-os/
  profiles/
  decisions/
  handoffs/
  tracker/
  dashboards/
  work/
  reports/
```

and a per-initiative work structure across product, architecture, app, database, quality, security, platform, DevOps, SRE, TPM, docs, design, data, AI, and more.

That part is good.

The issue is not the idea. The issue is **product shape**.

## Main problems to fix in the new plugin

### Problem 1: Too many skills

The current plugin has become a catalogue. You need a workflow system.

The new plugin should start with fewer skills that map to actual engineering lifecycle moments.

### Problem 2: Too many agents

127 agents is not a usable set of defaults. Most should become reference material, not active agents.

### Problem 3: Hooks are too broad

Your current `hooks.json` has many hooks across `SessionStart`, `Stop`, `Notification`, `PreToolUse`, `PostToolUse`, and `PreCompact`.

That is powerful, but it risks becoming noisy and hard to debug. The new plugin should split hooks into:

```text
core hooks       always useful
safety hooks     block dangerous behaviour
hygiene hooks    suggest or patch supporting files
optional hooks   disabled unless enabled
```

### Problem 4: Possible convention drift

One thing to clean up: your `engineering-os/CONVENTIONS.md` says not to add `displayName`, explicit `hooks`, and other fields because they may conflict with older validation behaviour.

But the current `plugin.json` includes both `displayName` and an explicit `hooks` path.

This may be harmless on your current Claude Code version, but it is a good example of why the new plugin needs **one authoritative schema rule** and validation.

---

# 3. Design principle for the new plugin

The new plugin should be organised around **decisions and artefacts**, not around departments.

Instead of:

```text
product plugin
architecture plugin
frontend plugin
backend plugin
database plugin
security plugin
devops plugin
quality plugin
docs plugin
```

Use:

```text
discover the product
define the requirements
map the system
design the architecture
plan the implementation
build safely
review the change
release safely
maintain the repo
```

This creates a smaller and more useful plugin.

---

# 4. Proposed plugin structure

```text
engineering-lifecycle/
  .claude-plugin/
    plugin.json

  README.md
  CHANGELOG.md
  LICENSE

  skills/
    profile-product-system/
      SKILL.md
      templates/product-system-profile.yaml
      examples/example-profile.yaml

    map-product-lifecycle/
      SKILL.md
      templates/lifecycle-map.md
      examples/example-lifecycle-map.md

    create-discovery-brief/
      SKILL.md
      templates/discovery-brief.md

    create-prd/
      SKILL.md
      templates/prd.md

    create-ux-flow/
      SKILL.md
      templates/ux-flow.md
      templates/screen-inventory.md

    create-system-map/
      SKILL.md
      templates/system-map.md
      templates/context-diagram.mmd
      templates/container-diagram.mmd

    create-architecture-plan/
      SKILL.md
      templates/architecture-plan.md
      templates/adr.md

    create-data-model/
      SKILL.md
      templates/entity-model.md
      templates/erd.mmd

    create-api-contract/
      SKILL.md
      templates/api-contract.md
      templates/openapi-fragment.yaml

    create-implementation-plan/
      SKILL.md
      templates/implementation-plan.md
      templates/task-breakdown.md

    implement-feature-safely/
      SKILL.md
      templates/implementation-log.md

    review-change/
      SKILL.md
      templates/change-review.md

    create-test-strategy/
      SKILL.md
      templates/test-strategy.md

    create-release-plan/
      SKILL.md
      templates/release-plan.md

    run-engineering-council/
      SKILL.md
      templates/council-input.json
      templates/council-report.md

    update-repo-hygiene/
      SKILL.md
      templates/repo-hygiene-report.md

    build-project-dashboard/
      SKILL.md
      templates/dashboard-data.json

  agents/
    product-discovery-lead.md
    requirements-analyst.md
    ux-flow-designer.md
    solution-architect.md
    domain-modeller.md
    api-contract-reviewer.md
    frontend-engineer.md
    backend-engineer.md
    database-engineer.md
    security-reviewer.md
    qa-test-strategist.md
    devops-release-engineer.md
    repo-hygiene-maintainer.md
    council-contrarian.md
    council-first-principles.md
    council-expansionist.md
    council-outsider.md
    council-executor.md
    council-chairperson.md

  hooks/
    hooks.json
    scripts/
      session-start-context.sh
      block-secret-exfil.sh
      block-dangerous-bash.sh
      detect-new-env-vars.py
      update-env-example.py
      suggest-gitignore-updates.py
      hygiene-stop-check.py
      validate-generated-artifacts.py
      sync-ledger.py
      capture-session-summary.py

  scripts/
    init-workspace.py
    profile-repo.py
    generate-mermaid-index.py
    validate-artifact.py
    validate-plugin.py
    validate-schemas.py
    emit-action-items.py
    sync-ledger.py
    council.py

  bin/
    eng-life
    eng-council
    eng-hygiene

  references/
    lifecycle-model.md
    architecture-mapping-guide.md
    data-modelling-guide.md
    testing-strategy-guide.md
    repo-hygiene-rules.md
    hook-safety-model.md
    council-design.md

  templates/
    handoff.template.json
    action-items.template.json
    human-tasks.template.json
    adr.template.md
    prd.template.md
    system-map.template.md

  schemas/
    product-system-profile.schema.json
    lifecycle-map.schema.json
    handoff.schema.json
    action-items.schema.json
    human-tasks.schema.json
    repo-hygiene.schema.json
    council-report.schema.json

  examples/
    full-lifecycle-example/
      01-discovery-brief.md
      02-prd.md
      03-ux-flow.md
      04-system-map.md
      05-architecture-plan.md
      06-data-model.md
      07-implementation-plan.md
      08-test-strategy.md
      09-release-plan.md

  evals/
    evals.json
    trigger-evals.json
    fixtures/
```

---

# 5. Plugin manifest

Keep the manifest simple.

```json
{
  "name": "engineering-lifecycle",
  "displayName": "Engineering Lifecycle",
  "version": "0.1.0",
  "description": "Plan, map, design, implement, review, test, release, and maintain software products through a structured engineering lifecycle.",
  "author": {
    "name": "John O'Connor",
    "email": "admin@igeneratedigital.com"
  },
  "repository": "https://github.com/anthril/anthril-os",
  "license": "MIT",
  "keywords": [
    "engineering",
    "architecture",
    "product",
    "software-development",
    "devops",
    "testing",
    "repo-hygiene"
  ]
}
```

The current docs support explicit manifest fields such as name, displayName, version, description, author, repository, license, keywords, skills, commands, agents, hooks, MCP servers, output styles, LSP servers, monitors, and dependencies. ([Claude][2])

However, I would initially rely on default component discovery rather than over-specifying paths unless validation confirms the current CLI handles every field cleanly.

---

# 6. Core skills

## Skill 1: `profile-product-system`

Purpose:

> Understand the current product, users, business context, repo structure, stack, integrations, constraints, and development maturity.

Use this at the start of any project.

Outputs:

```text
.anthril/.engineering-lifecycle/profile/product-system-profile.yaml
.anthril/.engineering-lifecycle/profile/tech-stack-profile.yaml
.anthril/.engineering-lifecycle/profile/repo-profile.yaml
```

Key sections:

* Product summary
* User types
* External systems
* Tech stack
* Deployment model
* Data stores
* Known constraints
* Current risks
* Development maturity
* Missing information

---

## Skill 2: `map-product-lifecycle`

Purpose:

> Map where the product currently sits in the software lifecycle and what artefacts are missing.

Outputs:

```text
lifecycle-map.md
lifecycle-state.yaml
missing-artifacts.json
```

Lifecycle stages:

```text
Discovery
Requirements
UX design
Architecture
Data model
Development
Testing
Release
Monitoring
Maintenance
```

This becomes the plugin’s “home base.”

---

## Skill 3: `create-discovery-brief`

Purpose:

> Convert a vague product idea into a clear discovery brief.

Outputs:

* Problem statement
* Target users
* Use cases
* Business goals
* Success metrics
* Risks
* Assumptions
* Open questions
* MVP boundary

---

## Skill 4: `create-prd`

Purpose:

> Produce a practical product requirements document.

Outputs:

* Functional requirements
* Non-functional requirements
* User stories
* Acceptance criteria
* Edge cases
* Permissions
* Analytics requirements
* Release assumptions

---

## Skill 5: `create-ux-flow`

Purpose:

> Map user journeys, screens, states, and interaction flows.

Outputs:

* User flow
* Screen inventory
* Component inventory
* Empty states
* Loading states
* Error states
* Permission states
* Accessibility considerations

---

## Skill 6: `create-system-map`

Purpose:

> Identify users, external systems, workflows, components, data flow, responsibilities, failure points, security, deployment, and infrastructure.

This directly maps to what you asked for:

```text
Identify users and external systems
Map major product workflows
Map system components
Map data entities
Map data flow
Map responsibilities and boundaries
Map failure points
Map security and permissions
Map deployment and infrastructure
```

Outputs:

* System context diagram
* Container diagram
* Workflow map
* Component inventory
* External integration map
* Failure-point map
* Security boundary map

---

## Skill 7: `create-architecture-plan`

Purpose:

> Turn the system map into an implementable architecture plan.

Outputs:

* Architecture overview
* Module boundaries
* Deployment model
* Build vs buy decisions
* ADRs
* Scaling considerations
* Security decisions
* Observability requirements
* Technical risks

---

## Skill 8: `create-data-model`

Purpose:

> Design entities, relationships, ownership boundaries, and data lifecycle.

Outputs:

* Entity relationship model
* Data dictionary
* Ownership model
* Sensitive data classification
* Audit log requirements
* Retention rules
* Migration risks

---

## Skill 9: `create-api-contract`

Purpose:

> Define interfaces between frontend, backend, services, agents, and external systems.

Outputs:

* REST / RPC / GraphQL contract
* Request / response shapes
* Error model
* Auth requirements
* Pagination
* Rate limits
* Webhooks
* Event contracts

---

## Skill 10: `create-implementation-plan`

Purpose:

> Break a design into safe, sequenced engineering work.

Outputs:

* Epics
* Tasks
* Dependencies
* Migration steps
* Test requirements
* Rollback plan
* “Do first / do later” split
* Human approvals required

---

## Skill 11: `implement-feature-safely`

Purpose:

> Guide actual implementation while respecting architecture, tests, repo conventions, and hygiene rules.

This should be **manual-invocation only** or strongly permissioned.

It should:

* inspect existing code first
* produce a plan
* identify files likely to change
* implement small slices
* run relevant tests
* update docs
* update `.env.example` if env vars changed
* update `.gitignore` if generated or local files appeared
* emit an implementation log

---

## Skill 12: `review-change`

Purpose:

> Review a branch, PR, diff, or uncommitted change.

Review dimensions:

* correctness
* architecture boundaries
* test coverage
* security
* error handling
* observability
* migration safety
* maintainability
* unnecessary complexity
* under-engineering
* hidden coupling

This should map strongly to your earlier code audit checklist.

---

## Skill 13: `create-test-strategy`

Purpose:

> Design the correct test plan for the product or feature.

Outputs:

* Unit tests
* Integration tests
* Contract tests
* E2E tests
* Regression tests
* Load tests
* Security tests
* AI evals if relevant
* Manual QA checklist

---

## Skill 14: `create-release-plan`

Purpose:

> Convert completed engineering work into a safe release.

Outputs:

* Release checklist
* Migration checklist
* Feature flag plan
* Rollback plan
* Monitoring plan
* Support notes
* Changelog
* Post-release validation

---

## Skill 15: `run-engineering-council`

Purpose:

> Use the LLM council for high-stakes decisions.

This should be invoked manually:

```text
/engineering-lifecycle:run-engineering-council "Should we build this as a modular monolith or microservices?"
```

It should use your council design as the foundation: independent role-specialised advisors, anonymisation, peer review, chair synthesis, failure handling, and observability. 

---

## Skill 16: `update-repo-hygiene`

Purpose:

> Inspect repo hygiene and safely update supporting files.

Checks:

* `.gitignore`
* `.env.example`
* `.dockerignore`
* `.npmignore`
* `README.md`
* `CHANGELOG.md`
* `CLAUDE.md`
* package scripts
* test commands
* generated files
* local-only files
* secrets accidentally created
* missing example config

This is the skill version of your hook idea.

Hooks should detect and suggest.
This skill should make intentional updates.

---

# 7. Agent design

Keep agents around **15 to 20 maximum**.

## Recommended agents

```text
product-discovery-lead
requirements-analyst
ux-flow-designer
solution-architect
domain-modeller
api-contract-reviewer
frontend-engineer
backend-engineer
database-engineer
security-reviewer
qa-test-strategist
devops-release-engineer
repo-hygiene-maintainer
documentation-maintainer
technical-program-manager
```

## Council agents

```text
council-contrarian
council-first-principles
council-expansionist
council-outsider
council-executor
council-chairperson
```

## Tool permissions

Default posture:

```yaml
tools: Read, Glob, Grep
```

For review agents:

```yaml
tools: Read, Glob, Grep, Bash
```

For implementation agents:

```yaml
tools: Read, Glob, Grep, Bash, Edit, Write
```

For council advisors:

```yaml
tools: Read, Glob, Grep
```

For council chairperson:

```yaml
tools: Read, Glob, Grep, Write
```

This follows the principle that subagents can enforce constraints by limiting tool access, while specialist prompts preserve context in the main session. ([Claude][4])

---

# 8. Hook design

Hooks should be **deterministic and narrow**.

Do not make hooks do complex product reasoning. Use hooks for things that can be checked reliably.

## Core hooks

### `SessionStart`

Purpose:

* detect repo root
* detect package manager
* detect framework
* initialise `.anthril/.engineering-lifecycle/` only if already present or explicitly enabled
* load a short context summary
* detect current branch

Possible scripts:

```text
session-start-context.sh
detect-stack.py
load-project-state.py
```

Claude docs say `SessionStart` runs every session, so these must be fast. ([Claude][6])

---

### `PreToolUse`

Purpose:

* block dangerous commands
* block obvious secret exfiltration
* block destructive database operations unless explicitly approved
* block source edits if the current mode is planning/review only

Possible scripts:

```text
block-dangerous-bash.sh
block-secret-exfil.sh
block-production-db.sh
mode-gate.py
```

Hooks can block actions using exit code 2 or structured decisions depending on event type. ([Claude][6])

---

### `PostToolUse`

Purpose:

* after file writes/edits, detect hygiene drift
* detect new env vars
* detect generated files
* validate markdown front matter
* validate JSON/YAML schemas
* emit ledger items
* suggest docs updates

Possible scripts:

```text
detect-new-env-vars.py
suggest-gitignore-updates.py
validate-generated-artifacts.py
sync-ledger.py
```

Important: PostToolUse should usually **not silently edit source files**. It should either:

1. write a hygiene report, or
2. return additional context telling Claude what needs to be fixed, or
3. call a narrowly scoped script that updates only approved support files.

---

### `Stop`

Purpose:

* inspect final response
* check whether the task claims completion
* verify supporting artefacts exist
* suggest next lifecycle skill
* remind about hygiene updates
* optionally block stop if a goal-specific completion condition is unmet

Claude’s `/goal` is effectively a session-scoped prompt-based Stop hook, but a plugin Stop hook is better for deterministic checks. ([Claude][8])

Possible scripts:

```text
hygiene-stop-check.py
completion-contract-check.py
suggest-next-skill.py
```

---

# 9. Repo hygiene automation design

Your example is exactly right:

> “A hook that runs at the end of a session or plan completion that automatically updates the `.gitignore` file or adds new credentials to `.env.example`.”

I would implement this as a **two-tier system**.

## Tier 1: automatic detection

Runs after edits.

Detect:

* new files not tracked by git
* generated files
* local database files
* log files
* cache directories
* env vars introduced in code
* secrets-like variable names
* new config files
* new ports
* new package scripts
* new Docker/service dependencies

Output:

```text
.anthril/.engineering-lifecycle/hygiene/hygiene-report.json
.anthril/.engineering-lifecycle/hygiene/hygiene-report.md
```

## Tier 2: controlled update

The plugin may update these files only when safe:

```text
.env.example
.gitignore
.dockerignore
README.md
CHANGELOG.md
CLAUDE.md
```

Rules:

```text
.env.example:
  Add variable names only.
  Never copy actual values.
  Use placeholder values.
  Preserve comments where possible.

.gitignore:
  Add only known generated/local patterns.
  Do not ignore source directories.
  Do not ignore lockfiles unless policy allows it.

README.md:
  Suggest changes by default.
  Edit only when the user asked for docs updates.

CHANGELOG.md:
  Append under Unreleased only.
  Do not invent version numbers.

CLAUDE.md:
  Add durable project conventions only.
  Do not add transient task notes.
```

## Example hygiene report

```json
{
  "new_env_vars": [
    {
      "name": "STRIPE_WEBHOOK_SECRET",
      "seen_in": ["src/billing/webhook.ts"],
      "in_env_example": false,
      "recommended_placeholder": "STRIPE_WEBHOOK_SECRET=whsec_example"
    }
  ],
  "gitignore_candidates": [
    {
      "pattern": ".turbo/",
      "reason": "Generated build cache detected",
      "safe_to_add": true
    }
  ],
  "docs_updates": [
    {
      "file": "README.md",
      "reason": "New webhook setup required",
      "safe_to_auto_edit": false
    }
  ]
}
```

---

# 10. Workspace contract

I would keep your `.anthril` concept, but simplify the path.

Current:

```text
.anthril/.eng-os/
```

Recommended:

```text
.anthril/.engineering-lifecycle/
```

Suggested structure:

```text
.anthril/.engineering-lifecycle/
  profile/
    product-system-profile.yaml
    tech-stack-profile.yaml
    repo-profile.yaml

  initiatives/
    <initiative-id>/
      discovery/
      requirements/
      ux/
      architecture/
      data/
      api/
      implementation/
      testing/
      release/
      security/
      observability/
      docs/

  decisions/
    ADR-0001-example.md

  handoffs/
    <timestamp>-<from>-to-<to>.json

  hygiene/
    hygiene-report.json
    hygiene-report.md

  ledger/
    ledger.json
    ledger-log.jsonl

  council/
    <run-id>/
      input.json
      advisor-drafts/
      peer-reviews/
      synthesis.md
      events.jsonl

  dashboards/
    project-dashboard.html

  reports/
```

This keeps your existing strongest idea — a local structured engineering workspace — but makes it easier to understand.

---

# 11. Artefact lifecycle

Each major output should have front matter.

```yaml
---
initiative_id: checkout-rebuild-2026-q3
skill: create-architecture-plan
created_at: 2026-06-27T14:00:00+10:00
status: draft
confidence: medium
source_profile: .anthril/.engineering-lifecycle/profile/product-system-profile.yaml
---
```

Recommended statuses:

```text
draft
reviewed
approved
implemented
superseded
```

For ADRs:

```text
proposed
accepted
superseded
rejected
```

For action items:

```text
open
in-progress
blocked
done
deferred
cancelled
```

Your current repo already has a useful action-item / human-task ledger concept, where emitted items are normalised into sidecar files and synced into a central ledger.

I would preserve that pattern.

---

# 12. Architecture mapping workflow

This should be one of the strongest parts of the plugin.

## Input

```text
/engineering-lifecycle:create-system-map "Map the current SaaS application architecture and identify missing docs"
```

## Process

The skill should:

1. Inspect repo structure.
2. Identify app boundaries.
3. Identify users and actors.
4. Identify external systems.
5. Identify core workflows.
6. Identify data entities.
7. Identify data flows.
8. Identify ownership boundaries.
9. Identify failure points.
10. Identify auth and permissions.
11. Identify deployment shape.
12. Produce diagrams and a written map.
13. Emit missing-info questions.
14. Emit action items.

## Output

```text
system-map.md
context-diagram.mmd
container-diagram.mmd
component-map.md
data-flow-map.md
security-boundaries.md
failure-modes.md
```

## Example system-map sections

```markdown
# System Map

## 1. Product context

## 2. Users and actors

## 3. External systems

## 4. Major workflows

## 5. System components

## 6. Data entities

## 7. Data flow

## 8. Responsibility boundaries

## 9. Failure points

## 10. Security and permissions

## 11. Deployment and infrastructure

## 12. Observability

## 13. Missing information

## 14. Recommended next artefacts
```

---

# 13. LLM council design

I would include the council as an **optional high-stakes decision engine**, not as the main workflow engine.

Your uploaded design is strong because it includes:

* role-specialised advisors
* independent fan-out
* anonymisation
* blind peer review
* chairperson synthesis
* quorum-based failure handling
* observability events
* record/replay fixtures for deterministic tests 

## Recommended council skill

```text
skills/run-engineering-council/SKILL.md
```

## Recommended council CLI

```text
bin/eng-council
```

Example:

```bash
eng-council ask \
  --question "Should we use Supabase or a custom Postgres backend?" \
  --context .anthril/.engineering-lifecycle/initiatives/mvp/architecture/
```

## Council roles

Use your existing proposed roles:

```text
Contrarian
First-Principles Thinker
Expansionist
Outsider
Executor
Chairperson
```

## When to use council

Use it for:

* architecture choice
* data model trade-off
* security-sensitive feature
* risky migration
* scaling strategy
* build vs buy
* AI system design
* pricing / packaging decisions if engineering-heavy
* “are we over-engineering this?” decisions

Do not use it for:

* simple bug fixes
* basic refactors
* small UI changes
* obvious test failures
* routine docs updates
* repo hygiene checks

## Council output

```markdown
# Engineering Council Report

## Question

## Context reviewed

## Advisor positions

## Blind peer review summary

## Chairperson recommendation

## Dissent log

## Decision

## Next actions

## Confidence

## Follow-up artefacts
```

---

# 14. MCP, LSP, and external integrations

## MCP

Do **not** bundle live MCP servers in v0.1 unless they are essential.

Reason: MCP config often requires environment variables, credentials, and user-specific setup. Your current conventions already warn that auto-starting MCP servers with unset env vars can fail.

Instead:

```text
examples/mcp/
  github.mcp.example.json
  supabase.mcp.example.json
  playwright.mcp.example.json
  posthog.mcp.example.json
```

## LSP

LSP is valuable, but I would not ship custom LSP servers. The Claude docs recommend using official LSP plugins for common languages and only creating custom LSP plugins when needed for unsupported languages. ([Claude][2])

Ship:

```text
.lsp.json
```

as `{}` initially, plus docs explaining recommended companion LSP plugins.

## External systems to plan for

Reference docs should include mapping templates for:

```text
GitHub
Supabase
PostHog
Stripe
Vercel
Cloudflare
Google Ads API
OpenAI / Anthropic / model gateway
Email provider
CRM
Analytics warehouse
```

But do not hardwire them until needed.

---

# 15. Evaluation system

You should include evals from the start.

AgentSkills recommends testing skills with realistic prompts, expected outputs, optional files, varied phrasing, and edge cases. ([Agent Skills][9])

## Evaluation types

### 1. Trigger evals

Test whether the right skill activates.

Example:

```json
[
  {
    "query": "Can you map the architecture of this repo and show external systems?",
    "should_trigger": "create-system-map"
  },
  {
    "query": "Review this PR for architecture drift and test gaps",
    "should_trigger": "review-change"
  },
  {
    "query": "Update .env.example after this Stripe webhook change",
    "should_trigger": "update-repo-hygiene"
  }
]
```

### 2. Output quality evals

Test whether generated artefacts include required sections.

### 3. Schema evals

Validate YAML / JSON sidecars.

### 4. Hook evals

Feed sample hook JSON into scripts.

Example:

```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"src/billing.ts"}}' \
  | hooks/scripts/detect-new-env-vars.py
```

### 5. Council evals

Use record/replay fixtures, as your council design suggests, so tests do not require live model calls every time. 

---

# 16. Minimum v0.1 build

Do not start with the full structure.

Build this first:

```text
engineering-lifecycle/
  .claude-plugin/plugin.json
  README.md
  CHANGELOG.md

  skills/
    profile-product-system/
    create-system-map/
    create-architecture-plan/
    create-implementation-plan/
    review-change/
    update-repo-hygiene/
    run-engineering-council/

  agents/
    solution-architect.md
    security-reviewer.md
    qa-test-strategist.md
    repo-hygiene-maintainer.md
    council-contrarian.md
    council-first-principles.md
    council-executor.md
    council-chairperson.md

  hooks/
    hooks.json
    scripts/
      block-secret-exfil.sh
      block-dangerous-bash.sh
      detect-new-env-vars.py
      suggest-gitignore-updates.py
      hygiene-stop-check.py

  scripts/
    init-workspace.py
    validate-artifact.py
    sync-ledger.py
    council.py

  references/
    lifecycle-model.md
    architecture-mapping-guide.md
    repo-hygiene-rules.md
    council-design.md

  templates/
    system-map.md
    architecture-plan.md
    implementation-plan.md
    change-review.md
    hygiene-report.md
    council-report.md

  schemas/
    hygiene-report.schema.json
    action-items.schema.json
    council-report.schema.json

  evals/
    evals.json
    trigger-evals.json
```

That is enough to be genuinely useful without recreating the current bloat.

---

# 17. Suggested implementation phases

## Phase 1: Product shape

Deliverables:

* plugin name
* README
* manifest
* lifecycle model
* workspace contract
* skill list
* agent list
* hook list

Decision to make:

```text
Is this replacing engineering-os, or living beside it as a cleaner v2?
```

My recommendation: **build beside it first**.

---

## Phase 2: Core planning skills

Build:

```text
profile-product-system
create-system-map
create-architecture-plan
create-implementation-plan
```

These are the highest leverage.

---

## Phase 3: Repo hygiene automation

Build:

```text
update-repo-hygiene
detect-new-env-vars.py
suggest-gitignore-updates.py
hygiene-stop-check.py
```

Keep automatic edits conservative.

---

## Phase 4: Review and testing

Build:

```text
review-change
create-test-strategy
validate-artifact.py
evals/
schemas/
```

---

## Phase 5: LLM council

Build:

```text
run-engineering-council
council.py
council agents
council schemas
council fixtures
```

Use your uploaded design as the foundation.

---

## Phase 6: Dashboard and ledger

Build:

```text
sync-ledger.py
build-project-dashboard
dashboard-data.json
project-dashboard.html
```

This can reuse concepts from the current tracker / ledger design.

---

# 18. The cleanest mental model

The plugin should behave like an engineering operating system, but with a much smaller command surface:

```text
Profile the system
  ↓
Map the product lifecycle
  ↓
Create missing artefacts
  ↓
Design architecture and data model
  ↓
Plan implementation
  ↓
Implement safely
  ↓
Review changes
  ↓
Test and release
  ↓
Maintain hygiene
  ↓
Track decisions and action items
```

The plugin should not try to be 181 different things. It should be the **workflow spine** that helps you and AI agents move software products through the development lifecycle without losing architecture, requirements, hygiene, or decision context.

[1]: https://code.claude.com/docs/en/skills "Extend Claude with skills - Claude Code Docs"
[2]: https://code.claude.com/docs/en/plugins-reference "Plugins reference - Claude Code Docs"
[3]: https://agentskills.io/skill-creation/optimizing-descriptions "Optimizing skill descriptions - Agent Skills"
[4]: https://code.claude.com/docs/en/sub-agents "Create custom subagents - Claude Code Docs"
[5]: https://code.claude.com/docs/en/hooks-guide "Automate actions with hooks - Claude Code Docs"
[6]: https://code.claude.com/docs/en/hooks "Hooks reference - Claude Code Docs"
[7]: https://code.claude.com/docs/en/agent-teams "Orchestrate teams of Claude Code sessions - Claude Code Docs"
[8]: https://code.claude.com/docs/en/goal "Keep Claude working toward a goal - Claude Code Docs"
[9]: https://agentskills.io/skill-creation/evaluating-skills "Evaluating skill output quality - Agent Skills"

---

Yes. I would add a dedicated **quality-control script layer** whose job is to make Claude’s output more reliable before, during, and after each task.

The key idea:

```text
User prompt
  ↓
Prompt/context preparation scripts
  ↓
Clarification / ambiguity gate
  ↓
Planning quality gate
  ↓
Execution guardrail scripts
  ↓
Artifact validation scripts
  ↓
Repo hygiene scripts
  ↓
Output scoring / continuous improvement
```

Claude Code hooks are well suited for this because they can run on lifecycle events like `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolBatch`, `Stop`, `TaskCreated`, and `TaskCompleted`, and hook scripts receive JSON context from Claude Code. ([Claude][1])

One important caveat: a normal shell hook cannot directly “force” Claude to call `AskUserQuestion` as a tool. What it can do is detect ambiguity and inject context telling Claude to ask structured questions, or intercept/handle `AskUserQuestion` when Claude calls it. Claude’s docs describe `AskUserQuestion` as a tool that asks one to four multiple-choice questions, and hooks can satisfy or defer that tool call using `updatedInput` / `permissionDecision`. ([Claude][2]) ([Claude][1])

---

# Recommended additional scripts

## 1. Prompt and intent quality scripts

These run **before Claude starts working**.

### `classify-user-intent.py`

**Hook:** `UserPromptSubmit`
**Purpose:** Classify the user’s request into a lifecycle mode.

Example modes:

```text
discovery
requirements
ux-design
architecture
data-model
implementation
review
testing
release
repo-hygiene
council-decision
unknown
```

Output:

```json
{
  "intent": "architecture",
  "confidence": "high",
  "recommended_skill": "create-system-map",
  "requires_clarification": false
}
```

This lets the plugin guide Claude toward the correct skill and avoid random skill drift.

---

### `prompt-quality-score.py`

**Hook:** `UserPromptSubmit`
**Purpose:** Score whether the prompt contains enough information to produce a high-quality answer.

Checks for:

* clear objective
* target repo/module/file
* expected output
* constraints
* success criteria
* whether edits are allowed
* whether tests should be run
* whether external systems are involved

Example output:

```json
{
  "score": 72,
  "missing": [
    "success criteria",
    "whether source edits are allowed"
  ],
  "risk": "medium"
}
```

If the score is low, it should inject context like:

```text
The prompt is missing success criteria and edit permissions. Ask a brief clarification question before implementing.
```

Claude Code supports adding hidden `additionalContext` from hooks to Claude’s context. ([Claude][1])

---

### `prompt-rewrite-suggestions.py`

**Hook:** `UserPromptSubmit` or manual script
**Purpose:** Convert vague user prompts into stronger internal task briefs.

Input:

```text
"fix the auth flow"
```

Output:

```markdown
## Interpreted task
Investigate and repair the authentication flow.

## Required context to inspect
- auth routes
- session handling
- middleware
- login UI
- tests
- recent diffs

## Before editing
- identify expected behaviour
- reproduce or locate failure
- map affected components

## Completion criteria
- bug cause explained
- minimal fix implemented
- relevant tests run
- no secrets exposed
```

This does not replace the user’s prompt. It gives Claude better working context.

---

### `skill-router.py`

**Hook:** `UserPromptSubmit`
**Purpose:** Decide which skill should be invoked or suggested.

Example:

```json
{
  "recommended_skill": "create-architecture-plan",
  "reason": "User asked to map components, workflows, data flow, and boundaries.",
  "secondary_skills": [
    "create-data-model",
    "create-test-strategy"
  ]
}
```

This is useful because your previous plugin suffered from “95% of skills do not get used.” A router helps the right few skills activate consistently.

---

## 2. Clarification scripts

These prevent Claude from charging into the wrong task.

### `clarification-gate.py`

**Hook:** `UserPromptSubmit`
**Purpose:** Decide whether the task needs clarification before work begins.

It should detect:

* unclear target
* multiple possible meanings
* dangerous production action
* missing credentials/environment
* uncertain write permission
* missing acceptance criteria
* ambiguous product/technical objective

Output:

```json
{
  "requires_clarification": true,
  "reason": "The user asked to implement a feature but did not specify whether source edits are allowed.",
  "questions": [
    {
      "question": "What mode should Claude use?",
      "options": ["Plan only", "Implement with edits", "Review existing code only"]
    }
  ]
}
```

Recommended behaviour:

* For normal chat: inject context telling Claude to ask the question.
* For Agent SDK / headless workflows: pair this with an `AskUserQuestion` handling hook.

---

### `ask-user-question-bridge.py`

**Hook:** `PreToolUse` on `AskUserQuestion`
**Purpose:** Handle Claude’s `AskUserQuestion` tool in a controlled way.

Use cases:

1. In interactive Claude Code, allow the question to appear.
2. In headless mode, defer the question to an external UI.
3. In CI/eval mode, answer automatically using fixture defaults.

Claude docs specifically describe the `AskUserQuestion` defer flow: Claude calls the tool, the `PreToolUse` hook can return `permissionDecision: "defer"`, the process exits with `stop_reason: "tool_deferred"`, the caller gathers an answer, resumes, and the hook returns `allow` with `updatedInput`. ([Claude][1])

Example output when answering programmatically:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {
      "questions": [
        {
          "question": "What mode should Claude use?",
          "header": "Mode",
          "options": [
            { "label": "Plan only" },
            { "label": "Implement with edits" }
          ]
        }
      ],
      "answers": {
        "What mode should Claude use?": "Plan only"
      }
    }
  }
}
```

---

### `ambiguity-patterns.py`

**Hook:** `UserPromptSubmit`
**Purpose:** Detect phrases that often cause poor output.

Examples:

```text
"fix this"
"make it better"
"clean up the repo"
"improve architecture"
"add tests"
"make production ready"
"review everything"
"do the whole thing"
```

Output should classify ambiguity:

```json
{
  "ambiguity_type": "scope",
  "severity": "high",
  "suggested_question": "Should I review the whole repo or a specific feature/module?"
}
```

---

## 3. Context-gathering scripts

These give Claude the right repo context before it reasons.

### `repo-context-pack.py`

**Hook:** `SessionStart`, `UserPromptSubmit`, or manual
**Purpose:** Generate a compact repo profile.

Reads:

* package files
* framework config
* directory structure
* test commands
* build commands
* deployment files
* env examples
* Docker files
* CI workflows
* database migrations
* API routes

Writes:

```text
.anthril/.engineering-lifecycle/context/repo-context.md
.anthril/.engineering-lifecycle/context/repo-context.json
```

This should be concise. Do not dump the whole repo into context.

---

### `detect-stack.py`

**Hook:** `SessionStart`
**Purpose:** Detect technology stack and available commands.

Example output:

```json
{
  "package_manager": "pnpm",
  "frameworks": ["Next.js", "React"],
  "backend": ["FastAPI"],
  "database": ["PostgreSQL", "Prisma"],
  "test_commands": {
    "unit": "pnpm test",
    "lint": "pnpm lint",
    "typecheck": "pnpm typecheck"
  }
}
```

This improves implementation and review quality because Claude knows what commands are real.

---

### `load-project-memory.py`

**Hook:** `SessionStart`
**Purpose:** Load durable project context from the plugin workspace.

Reads:

```text
.anthril/.engineering-lifecycle/profile/
.anthril/.engineering-lifecycle/decisions/
.anthril/.engineering-lifecycle/ledger/
```

Injects:

* current initiative
* active architecture decisions
* known constraints
* forbidden patterns
* test commands
* deployment assumptions

---

### `active-initiative-resolver.py`

**Hook:** `UserPromptSubmit`
**Purpose:** Resolve which initiative the task belongs to.

Example:

```json
{
  "initiative_id": "google-ads-audit-v2",
  "confidence": "medium",
  "reason": "Prompt references audit generation and recommendations."
}
```

This prevents outputs from being scattered across random directories.

---

## 4. Planning and decision quality scripts

These improve the plan before implementation begins.

### `plan-quality-gate.py`

**Hook:** `PreToolUse` on `ExitPlanMode` or `Stop`
**Purpose:** Validate that a plan is complete before Claude exits plan mode.

Checks:

* objective
* assumptions
* affected files
* risks
* rollback plan
* tests to run
* acceptance criteria
* security/privacy impact
* migration impact
* docs/hygiene updates

Claude’s docs list `ExitPlanMode` as the tool used to present a plan and ask for user approval before leaving plan mode. ([Claude][1])

---

### `architecture-decision-detector.py`

**Hook:** `PostToolBatch` or `Stop`
**Purpose:** Detect when Claude made a meaningful architecture decision but did not create/update an ADR.

Examples:

* chose queue vs sync processing
* changed database model
* introduced new service boundary
* added external provider
* added auth/permission model
* changed deployment topology

Output:

```json
{
  "decision_detected": true,
  "adr_required": true,
  "suggested_title": "ADR-0007-use-background-worker-for-audit-generation"
}
```

---

### `council-trigger-detector.py`

**Hook:** `UserPromptSubmit` or `Stop`
**Purpose:** Decide whether a task is high-stakes enough to recommend the LLM council.

Trigger when:

* irreversible architecture decision
* security-sensitive change
* unclear trade-off
* high cost/risk
* migration
* scaling strategy
* build vs buy
* AI model/eval design

Output:

```json
{
  "recommend_council": true,
  "reason": "This is a high-impact build-vs-buy decision with long-term architecture consequences."
}
```

Do not automatically run the council. Suggest it.

---

## 5. Implementation guardrail scripts

These reduce bad code changes.

### `edit-scope-guard.py`

**Hook:** `PreToolUse` on `Edit|Write`
**Purpose:** Prevent Claude from editing files outside the approved scope.

Reads:

```text
.anthril/.engineering-lifecycle/current-plan.json
```

Blocks or asks when Claude edits unrelated files.

Example:

```json
{
  "permissionDecision": "ask",
  "permissionDecisionReason": "This file is outside the approved implementation scope."
}
```

Claude’s `PreToolUse` hooks can deny, ask, allow, or modify tool inputs before a tool call runs. ([Claude][1])

---

### `dangerous-command-guard.sh`

**Hook:** `PreToolUse` on `Bash`
**Purpose:** Block dangerous shell commands.

Block:

```text
rm -rf /
rm -rf .
git reset --hard
git clean -fdx
docker system prune
drop database
truncate table
curl ... | sh
chmod -R 777
```

This should be deterministic, not LLM-based.

---

### `production-environment-guard.py`

**Hook:** `PreToolUse` on `Bash` and MCP write tools
**Purpose:** Detect commands targeting production.

Examples:

```text
DATABASE_URL=prod
vercel --prod
railway up
supabase db push --linked
kubectl apply
terraform apply
```

Return `ask` or `deny` unless the approved mode allows production actions.

---

### `secret-exfiltration-guard.py`

**Hook:** `PreToolUse` on `Bash`, `Write`, `Edit`, MCP tools
**Purpose:** Prevent secrets from being printed, copied, committed, or sent externally.

Detect:

* `.env`
* private keys
* API keys
* OAuth secrets
* database URLs
* service account JSON
* tokens in command args

This should be one of the first scripts implemented.

---

### `generated-file-guard.py`

**Hook:** `PreToolUse` on `Edit|Write`
**Purpose:** Detect edits to generated files.

If Claude tries to edit generated files, inject context:

```text
This appears to be generated. Edit the source schema/template instead and regenerate.
```

Claude hooks can add `additionalContext` so the model sees this guidance before continuing. ([Claude][1])

---

## 6. Post-edit validation scripts

These run after Claude edits or writes files.

### `changed-files-classifier.py`

**Hook:** `PostToolBatch`
**Purpose:** Classify all files touched in the turn.

Categories:

```text
source
test
docs
config
schema
migration
generated
secret-risk
build-artifact
unknown
```

This gives downstream scripts better routing.

---

### `env-example-sync.py`

**Hook:** `PostToolUse` on `Edit|Write`, plus manual skill
**Purpose:** Detect new environment variables and update `.env.example`.

Rules:

* never copy real values
* only add placeholder values
* preserve comments
* detect removed vars but do not auto-delete without confirmation
* group vars by subsystem

Example:

```dotenv
# Stripe
STRIPE_SECRET_KEY=sk_test_example
STRIPE_WEBHOOK_SECRET=whsec_example

# Anthropic
ANTHROPIC_API_KEY=sk-ant-example
```

---

### `gitignore-sync.py`

**Hook:** `PostToolUse` or `Stop`
**Purpose:** Suggest or apply safe `.gitignore` updates.

Safe additions:

```text
.env.local
*.log
.cache/
.turbo/
.vercel/
coverage/
dist/
build/
```

Unsafe additions requiring approval:

```text
package-lock.json
pnpm-lock.yaml
migrations/
schema/
src/
tests/
```

---

### `schema-validator.py`

**Hook:** `PostToolUse`
**Purpose:** Validate plugin artefacts and project JSON/YAML files against schemas.

Validate:

```text
action-items.json
human-tasks.json
handoff.json
product-system-profile.yaml
architecture-plan.yaml
repo-hygiene-report.json
council-report.json
```

---

### `markdown-artifact-validator.py`

**Hook:** `PostToolUse`
**Purpose:** Validate generated docs.

Checks:

* required headings exist
* front matter exists
* no unresolved placeholders
* links are valid enough
* Mermaid blocks parse
* status/confidence present
* source artefacts referenced

---

### `test-command-resolver.py`

**Hook:** manual / `PostToolBatch`
**Purpose:** Determine the smallest relevant test command after edits.

Example output:

```json
{
  "recommended_commands": [
    "pnpm typecheck",
    "pnpm test src/auth",
    "pnpm lint src/auth"
  ],
  "reason": "Auth-related TypeScript files changed."
}
```

This avoids Claude either running no tests or running the whole world unnecessarily.

---

### `test-result-parser.py`

**Hook:** `PostToolUse` on `Bash`
**Purpose:** Parse test/lint/typecheck output and inject a useful summary.

Output:

```json
{
  "command": "pnpm test",
  "status": "failed",
  "failures": [
    {
      "file": "src/auth/session.test.ts",
      "test": "refreshes expired token",
      "error": "Expected 200, received 401"
    }
  ]
}
```

This helps Claude fix the right issue rather than misreading long terminal output.

---

## 7. Completion quality scripts

These stop Claude from finishing too early.

### `completion-contract-check.py`

**Hook:** `Stop`
**Purpose:** Check whether Claude’s final response claims completion without meeting objective evidence.

Checks:

* required files created
* expected sections exist
* tests were run or explicitly not run
* generated artefacts validate
* plan tasks marked done
* hygiene report checked
* no unresolved blockers hidden in prose

If incomplete, return additional context:

```text
Before finishing, create the missing architecture decision record and run the schema validator.
```

Claude’s Stop hook can inject feedback such as “run the test suite before finishing,” keeping the task alive. ([Claude][1])

---

### `definition-of-done-check.py`

**Hook:** `TaskCompleted` or `Stop`
**Purpose:** Validate task completion against the task type.

Example definitions:

```text
Architecture task:
  system map created
  decisions listed
  risks listed
  ADRs created where needed
  open questions listed

Implementation task:
  code changed
  relevant tests run
  docs/hygiene checked
  no obvious secret leakage
  final summary includes changed files and validation

Review task:
  findings have severity
  findings cite files/lines
  recommendations are actionable
  false positives marked uncertain
```

---

### `final-answer-structure-check.py`

**Hook:** `Stop`
**Purpose:** Check final response quality.

For implementation tasks, require:

```text
Summary
Files changed
Validation performed
Risks / limitations
Next step
```

For planning tasks, require:

```text
Recommendation
Rationale
Trade-offs
Proposed structure
Implementation sequence
Open questions
```

---

## 8. Output optimisation scripts

These improve generated deliverables.

### `artifact-completeness-score.py`

**Hook:** `PostToolUse` or `Stop`
**Purpose:** Score each artefact against its template.

Example:

```json
{
  "artifact": "architecture-plan.md",
  "score": 86,
  "missing_sections": [
    "Failure modes",
    "Rollback strategy"
  ],
  "recommendation": "Revise before marking complete."
}
```

---

### `artifact-consistency-check.py`

**Hook:** `PostToolBatch`
**Purpose:** Ensure generated artefacts agree with each other.

Checks:

* PRD requirements appear in implementation plan
* architecture components appear in system map
* data entities match API contracts
* tests cover acceptance criteria
* release plan references migrations
* ADRs match architecture plan

---

### `naming-consistency-check.py`

**Hook:** `PostToolUse`
**Purpose:** Prevent naming drift.

Detect mismatches like:

```text
AuditRun vs AuditJob
Workspace vs Organisation
Finding vs Recommendation
ConnectedAccount vs IntegrationAccount
```

Output should recommend canonical names.

---

### `diagram-sync-check.py`

**Hook:** `PostToolUse`
**Purpose:** Ensure Mermaid diagrams match written architecture.

Checks:

* every diagram node appears in component list
* external systems are labelled
* security boundaries are represented
* data stores are represented
* no orphan components

---

### `example-output-validator.py`

**Hook:** `PostToolUse`
**Purpose:** Validate skill example outputs.

This is especially important for your plugin itself. Every skill should have at least one realistic example output, and this script should check whether examples match the current template.

---

## 9. Continuous improvement scripts

These help improve the plugin over time.

### `prompt-outcome-logger.py`

**Hook:** `UserPromptSubmit`, `Stop`, `StopFailure`
**Purpose:** Log prompt → skill → outcome metadata.

Store:

```json
{
  "timestamp": "...",
  "prompt_hash": "...",
  "intent": "architecture",
  "skill_used": "create-system-map",
  "clarification_required": false,
  "files_changed": 4,
  "tests_run": true,
  "completion_score": 91
}
```

Do not store sensitive prompt content by default.

---

### `skill-trigger-audit.py`

**Hook:** manual / scheduled
**Purpose:** Analyse which skills are used and which are dead weight.

Output:

```json
{
  "unused_skills": [
    "create-api-contract"
  ],
  "overlapping_skills": [
    ["create-system-map", "create-architecture-plan"]
  ],
  "poor_trigger_descriptions": [
    "update-repo-hygiene"
  ]
}
```

This directly prevents your new plugin from becoming the old messy one.

---

### `prompt-optimization-evaluator.py`

**Hook:** manual / eval suite
**Purpose:** Test skill descriptions and prompt templates against known user prompts.

Inputs:

```text
evals/trigger-evals.json
evals/output-evals.json
```

Outputs:

```text
evals/reports/prompt-optimization-report.md
```

This should recommend edits to:

* skill descriptions
* agent descriptions
* system prompts
* examples
* clarification questions
* output templates

---

### `failure-pattern-miner.py`

**Hook:** manual
**Purpose:** Analyse failed or low-quality sessions.

Detect:

* bad skill routing
* missing context
* premature implementation
* skipped tests
* hallucinated file paths
* over-editing
* weak final answer
* repeated clarification gaps

---

## 10. Security and safety scripts

### `sensitive-file-policy.py`

**Hook:** `PreToolUse` and `PostToolUse`
**Purpose:** Classify sensitive files and enforce safe handling.

Sensitive examples:

```text
.env
*.pem
*.key
service-account.json
credentials.json
id_rsa
database dumps
customer exports
```

Actions:

* block printing full contents
* prevent writing secrets to docs
* prevent copying into generated examples
* warn before editing

---

### `dependency-risk-check.py`

**Hook:** `PostToolUse` on package files
**Purpose:** Detect new dependencies and require justification.

Checks:

* new package added
* package is deprecated
* package has install scripts
* package overlaps existing dependency
* package increases attack surface

---

### `migration-risk-check.py`

**Hook:** `PostToolUse`
**Purpose:** Inspect database migrations.

Checks:

* destructive column/table drops
* nullable → non-null changes
* missing backfill
* missing transaction
* missing rollback
* large table risk
* index lock risk

---

### `api-contract-breaking-change-check.py`

**Hook:** `PostToolUse`
**Purpose:** Detect API breaking changes.

Checks:

* removed fields
* renamed endpoints
* changed status codes
* changed auth requirements
* incompatible response shape
* missing versioning

---

## 11. Council-specific scripts

### `council-input-builder.py`

**Manual / skill script**
**Purpose:** Build the best possible council prompt.

It should gather:

* question
* repo context
* relevant ADRs
* constraints
* current architecture
* prior attempts
* success criteria
* risk tolerance

---

### `council-role-runner.py`

**Manual / CLI**
**Purpose:** Run one advisor role independently.

Roles:

```text
contrarian
first-principles
expansionist
outsider
executor
```

---

### `council-anonymizer.py`

**Manual / CLI**
**Purpose:** Strip role labels before peer review.

This matches your uploaded LLM council design, where anonymisation is the trust boundary for blind review. 

---

### `council-peer-review.py`

**Manual / CLI**
**Purpose:** Run blind peer review over anonymised outputs.

---

### `council-synthesizer.py`

**Manual / CLI**
**Purpose:** Produce the Chairperson recommendation, dissent log, and action plan.

---

### `council-fixture-recorder.py`

**Manual / eval script**
**Purpose:** Record/replay council outputs for deterministic tests.

This is important because council workflows can become expensive and inconsistent if every eval requires live model calls.

---

# 12. Best script set for v0.1

For the first version, I would not build everything. I would implement these first:

```text
scripts/
  init-workspace.py
  detect-stack.py
  repo-context-pack.py
  classify-user-intent.py
  prompt-quality-score.py
  clarification-gate.py
  skill-router.py
  plan-quality-gate.py
  changed-files-classifier.py
  env-example-sync.py
  gitignore-sync.py
  test-command-resolver.py
  test-result-parser.py
  completion-contract-check.py
  artifact-completeness-score.py
  schema-validator.py
  prompt-optimization-evaluator.py
  council-input-builder.py
  council-synthesizer.py
```

And these hooks:

```text
hooks/scripts/
  user-prompt-intake.py
  ask-user-question-bridge.py
  block-dangerous-bash.sh
  secret-exfiltration-guard.py
  edit-scope-guard.py
  post-edit-hygiene.py
  stop-completion-check.py
```

---

# 13. Suggested hook mapping

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/init-workspace.py\""
          },
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/detect-stack.py\""
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/user-prompt-intake.py\""
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "AskUserQuestion",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/ask-user-question-bridge.py\""
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/block-dangerous-bash.sh\""
          },
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/secret-exfiltration-guard.py\""
          }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/edit-scope-guard.py\""
          }
        ]
      }
    ],
    "PostToolBatch": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-edit-hygiene.py\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/stop-completion-check.py\""
          }
        ]
      }
    ]
  }
}
```

---

# 14. The highest-value scripts overall

If I had to pick only ten, I would pick these:

| Priority | Script                             | Why it matters                            |
| -------: | ---------------------------------- | ----------------------------------------- |
|        1 | `classify-user-intent.py`          | Routes prompts to the right workflow      |
|        2 | `prompt-quality-score.py`          | Prevents weak outputs from weak prompts   |
|        3 | `clarification-gate.py`            | Forces missing requirements into the open |
|        4 | `repo-context-pack.py`             | Gives Claude the right project context    |
|        5 | `plan-quality-gate.py`             | Prevents shallow implementation plans     |
|        6 | `edit-scope-guard.py`              | Prevents uncontrolled codebase edits      |
|        7 | `secret-exfiltration-guard.py`     | Protects credentials and sensitive data   |
|        8 | `test-command-resolver.py`         | Makes validation practical and targeted   |
|        9 | `completion-contract-check.py`     | Stops premature “done” responses          |
|       10 | `prompt-optimization-evaluator.py` | Improves the plugin over time             |

My strongest recommendation: build the plugin around **intake quality**, **context quality**, **plan quality**, **execution safety**, and **completion proof**. That will improve output quality far more than adding another 50 skills.

[1]: https://code.claude.com/docs/en/hooks "Hooks reference - Claude Code Docs"
[2]: https://code.claude.com/docs/en/tools-reference "Tools reference - Claude Code Docs"
