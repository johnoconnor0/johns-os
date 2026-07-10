---
name: service-outline
description: Generate a new Service Outline or update an existing one from John's modular 10-part service template, adapted to the service type (consulting, AI engineering, software development, web design, AI-driven PPC, branding). Interviews for context first; accepts an uploaded file, file path, or Notion/web URL as an update source. Use when the user asks to write, draft, update, or scaffold a service outline, service document, service brief, or service definition.
argument-hint: "[service-name] [--type=<type>] [--new|--update <source>] [--brief] [--output=<path>] [--refresh] [--quick]"
---

# Service Outline

Generate and update professional **Service Outline** documents from a modular, service-type-aware template. An outline is assembled from 10 ordered modules; two of them — Technical/Security/Compliance and AI Service — are conditional **addenda** switched on by the service type and confirmed during the interview.

## Trigger

Use when the user asks to write, draft, create, update, refresh, or scaffold a service outline, service document, service definition, service brief, or service offering for one of the business's services.

## When To Use

- Defining a new service (consulting, AI engineering, software development, web design, AI-driven PPC, branding, or a custom type).
- Updating an existing service document from a file, local path, or Notion/web URL.
- Producing a short-form internal service brief (tiered Entry/Core/Premium) with `--brief`.

## Inputs Inspected

- `$ARGUMENTS` — service name, `--type`, mode (`--new` / `--update <source>`), `--brief`, `--output`, `--refresh`.
- The service-type profile at `skills/service-outline/templates/service-types/<type>.yaml` (addendum switches + seeded defaults).
- The bundled module templates at `skills/service-outline/templates/modules/`.
- For `--update`: the source document (file / path / Notion page / web URL) via the input adapters.
- Reference guides under `references/` (template structure, profiles, input adapters, interview guide, notion refresh).

## Workflow

1. **Parse arguments.** Resolve the service name, `--type`, mode, and flags. If there is no service name AND no update source AND no service described in the conversation, stop with `empty-argument` and ask for at least a service name or type.
2. **(Optional) Refresh templates.** If `--refresh` is set, re-pull the module templates from Notion before proceeding (see `references/notion-refresh.md`), confirming before overwriting the bundled files.
3. **Resolve the service-type profile.** Load `templates/service-types/<type>.yaml`. If `--type` is missing or unknown, use `generic.yaml` and infer the type during the interview. The profile declares which addenda are included and seeds defaults (typical tools, deliverables, timeline, pricing model, metrics, common risks).
4. **Ingest the source (update mode only).** For `--update <source>`, read the source with the matching adapter (see `references/input-adapters.md`): `Read` for an uploaded file or local path, the Notion MCP `notion-fetch` for a Notion URL, `WebFetch` for a web URL. Map its content onto the 10 modules and note which sections are present, thin, or outdated. For a large or multi-part source, delegate the module-by-module gap analysis to the read-only `service-document-analyst` agent and interview only the gaps it reports.
5. **Interview the user (mandatory gate — never write before this).** Using `AskUserQuestion`, ask a focused, batched set of questions from `references/interview-guide.md`, pre-filled from the profile and any ingested source. Ask only what is missing. If `--quick` is set, ask only the essentials (service name/type, target customer, core problem, primary deliverables) and both addendum triggers. Always confirm the two addendum triggers:
   - "Does this service handle personal/sensitive data or integrate with client systems?" → include module 08 (Technical, Security & Compliance Addendum).
   - "Does this service build or operate AI/LLM systems?" → include module 09 (AI Service Addendum).
6. **Assemble the outline.** Concatenate the included module templates in canonical order 01→10, filling field labels, `[bracketed]` placeholders, and tables from the interview answers, profile defaults, and any ingested source. Leave genuinely unknown values as `[TBC]` rather than inventing them.
7. **Write the artifact.** Write Markdown with front matter (see Outputs) to the output location. With `--brief`, also assemble `templates/internal-service-brief.template.md` into an internal brief.
8. **Validate.** Run `python scripts/validate-service-outline.py <path>` and resolve any reported missing modules or front-matter issues.
9. **Summarise.** Report what was written, which addenda were included/excluded and why, and every `[TBC]` left for the user to fill.

## Outputs

Default (overridable with `--output`):

- `.project/business-development/service-outlines/<service-slug>/service-outline.md`
- `.project/business-development/service-outlines/<service-slug>/internal-service-brief.md` (with `--brief`)

Front matter:

```yaml
---
service_name: "AI-Driven PPC Optimisation"
service_type: ai-ppc-optimisation
skill: service-outline
status: draft
created_at: 2026-07-10T00:00:00+10:00
source_template: notion-10-module
included_addenda: [technical-security-compliance, ai-service]
---
```

## Required Sections

Core modules (always included): Service Overview; Customer Fit and Qualification; Scope and Deliverables; Delivery Plan; Roles, Responsibilities, and Client Inputs; Success Measurement and Reporting; Risks, Dependencies, and Constraints; Support, Warranty, and Handover.

Conditional addenda (included when the service type / interview triggers them): Technical, Security, and Compliance Addendum; AI Service Addendum.

## Safety Constraints

- Never write an outline before completing the interview gate (or an explicit user override).
- Never invent client-specific facts, numbers, prices, or commitments — use `[TBC]`.
- Treat `--refresh` and any write-back to Notion as confirmation-gated, mutating actions.
- Do not include secrets, credentials, or private client data in generated documents.

## Related Agents

- `service-document-analyst` — read-only module-by-module gap analysis for `--update` sources.

## References

- `references/template-structure.md` — the faithful 10-module map (sections, tables, placeholders).
- `references/service-type-profiles.md` — how profiles pick addenda and seed defaults.
- `references/input-adapters.md` — ingesting a file / path / Notion URL / web URL.
- `references/interview-guide.md` — the question bank, grouped by module.
- `references/notion-refresh.md` — refreshing bundled templates from Notion.
