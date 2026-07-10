# Service Outline — template structure

The Service Outline is assembled from 10 ordered modules, bundled as Markdown partials in
`skills/service-outline/templates/modules/`. Concatenate the included modules in numeric
order (01 → 10) to form the full outline. Modules 8 and 9 are **conditional addenda**.

| # | Module | Always? | Load-bearing tables |
|---|--------|---------|---------------------|
| 1 | Service Overview | yes | — (labelled fields) |
| 2 | Customer Fit and Qualification | yes | — (discovery-question bank) |
| 3 | Scope and Deliverables | yes | Included scope; Deliverables |
| 4 | Delivery Plan | yes | Milestones |
| 5 | Roles, Responsibilities, and Client Inputs | yes | Stakeholders; Access; Approvals |
| 6 | Success Measurement and Reporting | yes | Measurement framework |
| 7 | Risks, Dependencies, and Constraints | yes | Risk register; Dependencies; Issues |
| 8 | Technical, Security, and Compliance Addendum | **conditional** | — |
| 9 | AI Service Addendum | **conditional** | Evaluation criteria |
| 10 | Support, Warranty, and Handover | yes | Severity levels; Maintenance ownership |

## Conventions

- Module titles are H2 (`## N. Title`); subsections are H3 (`### ...`).
- Fill-ins use `[bracketed placeholders]`; leave genuinely unknown values as `[TBC]`.
- Tables are load-bearing — keep their exact columns when filling them in.
- Pre-filled bullet lists (e.g. common risks, exclusions) are reusable boilerplate; prune
  and extend them per engagement rather than deleting the structure.

## Addendum selection

- **Module 8 (Technical, Security & Compliance)** — include when the service touches client
  systems, hosting, or personal/sensitive data.
- **Module 9 (AI Service)** — include when the service builds or operates AI/LLM systems.

The service-type profile pre-sets these (`true` / `false` / `interview`); the interview
always confirms them. See `service-type-profiles.md`.

## Short-form variant

`templates/internal-service-brief.template.md` is a one-page internal brief with a tiered
Entry/Core/Premium offer ladder and sales-qualification questions. Produced with `--brief`.
