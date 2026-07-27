---
name: create-prd
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*)
description: Use to produce a practical product requirements document with functional and non-functional requirements, user stories, acceptance criteria, assumptions, dependencies, success metrics, and release criteria.
---

# Create PRD

## Trigger

Use when the user asks for requirements, acceptance criteria, user stories, product
scope, success metrics, or a feature spec.

## When To Use

- After discovery is clear enough to define behaviour.
- Before UX, system mapping, technical design, or engineering planning.
- When scope needs to be testable.

## What Makes This Document Useful

A PRD earns its place by being **testable and bounded**. Two rules carry most of
that weight:

- **Every requirement must be verifiable.** If nobody can tell whether it is met,
  it is a wish. "The page should be fast" is a wish; "the product list renders
  within 1.5s at the 75th percentile on a 4G connection" is a requirement.
- **Requirements describe outcomes, not implementations.** Naming the database
  table in a PRD forecloses a design decision that has not been made yet. The
  exception is a genuine product constraint ("must remain usable offline"), which
  belongs here precisely because it is not the engineer's call.

## Inputs Inspected

- Discovery brief and product profile from the same initiative.
- Existing issues, docs, designs, and the user's prompt.
- Current behaviour in the codebase where the feature already partly exists.

## Workflow

1. Inspect discovery context, product profile, existing docs, issues and designs,
   and current behaviour before defining anything.
2. State the **problem** and who has it, then the **goals**, then **non-goals**.
3. Describe the **users** as roles with distinct needs and permissions, not
   demographics.
4. Write **user stories** in the form *As a `<role>`, I want `<capability>`, so that
   `<outcome>`*. The "so that" clause is the part that catches a feature nobody
   needs; do not omit it.
5. Convert goals into **functional requirements**, each individually verifiable and
   individually numbered so later artifacts can cite them.
6. Write **non-functional requirements** with numbers: performance, availability,
   scale, security, accessibility, compliance, supported browsers or devices.
7. Write **acceptance criteria** as Given/When/Then, tied to user-visible behaviour
   or an operational constraint:

   > **Given** a tenant admin with 5,000 audit events
   > **When** they export a filtered date range
   > **Then** the file contains only their tenant's events, and download begins
   > within 10 seconds.

8. Record **assumptions** (things believed true but unverified) and **dependencies**
   (other teams, systems, vendors, or work that must land first). Both change the
   plan if wrong, which is why they are written down rather than carried in
   someone's head.
9. Define **success metrics**: how you will know afterwards whether this worked,
   with the current baseline where one exists. "Adoption" is not a metric; "40% of
   active tenants run at least one export within 30 days" is.
10. Define **release criteria**: what must be true to ship. This is distinct from
    acceptance criteria, which describe correct behaviour.
11. Split must-have scope from later enhancements, and record explicit
    **out of scope** decisions.
12. Capture **open questions** whose answers would change scope, acceptance
    criteria or release risk. These are scraped into the open-questions store
    automatically, so write them as a list, one question per line.
13. Validate:

    ```bash
    python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" <artifact paths>
    ```

## Outputs

- `.project/docs/engineering/<initiative-id>/prd.md`

## Required Sections

- Problem
- Goals
- Non-Goals
- Users
- User Stories
- Functional Requirements
- Non-Functional Requirements
- Permissions And Data Handling
- Assumptions
- Dependencies
- Success Metrics
- Acceptance Criteria
- Release Criteria
- Edge Cases
- Out Of Scope
- Open Questions

## Required Front Matter

- `initiative_id`
- `skill`
- `created_at`
- `status`
- `confidence`
- `source_artifacts`

## Safety Constraints

- Do not over-specify implementation unless it is a genuine product constraint.
- Separate must-have requirements from later enhancements.
- Keep acceptance criteria measurable, and success metrics baselined.
- Never invent usage figures, user counts or conversion rates. If a baseline is
  unknown, write "unknown" and make finding it an open question.
- Distinguish confirmed requirements from proposed ones.

## Related Agents

- `requirements-analyst`
- `product-discovery-lead`
- `qa-test-strategist`
