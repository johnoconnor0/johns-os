---
name: create-technical-design-document
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*)
description: Use to turn product and system understanding into a technical design document - context, detailed design per component, data and API design, cross-cutting concerns, environments (preview/development/production), alternatives considered, and ADR candidates.
---

# Create Technical Design Document

## Trigger

Use when the user asks for a technical design, architecture, technical direction,
module boundaries, design tradeoffs, scaling shape, environment setup, or ADRs.

## When To Use

- After system mapping, before data model, API contract and engineering planning.
- When a technical decision has meaningful tradeoffs that outlive the change.
- When someone new needs to understand how a system is meant to work.

## What This Document Is For

A technical design document exists so a competent engineer who was not in the room
can implement the thing, and so the next person can find out **why** it is the way
it is. It is not a specification of what the code already does.

Two failure modes to avoid:

- **A description dressed as a design.** If every section describes the current
  code and nothing states a decision or a rejected alternative, this is
  documentation, not design.
- **A design with no non-goals.** Scope that is never bounded expands during
  implementation, and the document stops matching what gets built.

## Inputs Inspected

- System map, PRD, UX flow, and product profile from the same initiative.
- `context/stack.json` for the detected stack, and existing package boundaries.
- Prior decisions under `.project/.engineering/decisions/`.
- Current deployment configuration: CI workflows, Dockerfiles, `wrangler.toml`,
  `vercel.json`, `.env.example`, infrastructure definitions.

## Workflow

1. Inspect upstream artifacts and current code boundaries before recommending anything.
2. Write **Context and Scope**, then **Non-Goals**. Bound the work before designing it.
3. List constraints, operational assumptions, and decisions already made elsewhere.
4. Write **Detailed Design** per component: responsibility, interface, dependencies,
   failure behaviour.
5. Write **Data Design**, linking to the initiative's `data/schema.sql` rather than
   duplicating it. If no data model exists yet, say so and name what it must cover.
6. Write **API And Integration Design**: boundaries, protocols, auth, idempotency,
   versioning, and what happens when each dependency is unavailable.
7. Write **Cross-Cutting Concerns**: authentication and authorisation, logging and
   observability, error handling, configuration, internationalisation, rate limits.
8. Write **Environments** (see below). This is where most designs are silently
   incomplete.
9. Record **Alternatives Considered** with the reason each was rejected. An
   alternatives section with no rejected options is not a real one.
10. Create **ADR candidates** for decisions that affect durable architecture or
    operations. Check `.project/.engineering/decisions/` for the next free number.
11. Convene `run-engineering-council` for high-stakes, irreversible, or
    cross-cutting decisions before finalising. The prompt intake also flags these.
12. Validate:

    ```bash
    python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" <artifact paths>
    ```

## Environments

Design the environments alongside the system, not after it. For **preview**,
**development** and **production**, state:

| Question | Why it matters |
| --- | --- |
| What runs it? | Local process, Docker Compose, a hosted preview, a managed platform. |
| What backing services does it need? | Database, cache, queue, object storage, third-party APIs. |
| Where does its data come from? | Seed script, anonymised snapshot, live data, empty. |
| How is configuration supplied? | Env vars, secret manager, platform config. Never committed. |
| What is different from production, and why? | Every difference is a class of bug that only appears in production. |
| How does a change reach it? | Push, PR, tag, manual promotion. |
| How do you know it is healthy? | Health check, logs, error tracking. |

Rules:

- **Name every environment variable the design introduces**, and add each to
  `.env.example` with a placeholder. The `detect-new-env-vars` hook checks this,
  and it only works if the design lists them.
- **Docker is a decision, not a default.** If the stack needs a database, a queue
  or a service the host does not have, a Compose file earns its place. For a
  single-process app against a managed database, it adds a layer for nothing. Say
  which case this is.
- **Preview environments need a data story.** "It uses production" is a decision
  with security consequences, and it must be stated, not assumed.
- **Record what production has that development does not** (TLS termination, a
  CDN, connection pooling, read replicas, rate limits). Those gaps are where
  works-on-my-machine comes from.

## Outputs

- `.project/docs/engineering/<initiative-id>/technical-design-document.md`
- `.project/.engineering/decisions/ADR-<number>-<slug>.md`

## Required Front Matter

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

## Required Sections

- Context And Scope
- Non-Goals
- Constraints
- Recommended Architecture
- Detailed Design
- Data Design
- API And Integration Design
- Interfaces And Boundaries
- Cross-Cutting Concerns
- Environments
- Alternatives Considered
- Risks
- Migration And Rollback
- ADR Candidates
- Open Questions

## Safety Constraints

- Distinguish recommended decisions from alternatives considered.
- Do not invent operational constraints, SLAs or traffic figures. Mark them unknown.
- Never write real credentials, connection strings or endpoints. Placeholders only.
- Reserve council review for high-stakes, irreversible, or cross-cutting decisions.
- Record unresolved questions under Open Questions; they are scraped into the
  open-questions store automatically.

## Related Agents

- `solution-architect`
- `security-reviewer`
- `database-engineer`
- `devops-release-engineer`
