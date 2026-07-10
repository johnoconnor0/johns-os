# Business Development

A Claude Code + Codex plugin for authoring professional **Service Outline** documents from a
modular, service-type-aware template. Built to grow — the first skill is `service-outline`;
proposals, statements of work, and case studies are candidate future skills.

## Skill: `service-outline`

Generate a new Service Outline or update an existing one. The outline is assembled from 10
ordered modules; two of them are conditional **addenda** switched on by the service type and
confirmed during an interview.

```
/service-outline [service-name] [--type=<type>] [--new|--update <source>] [--brief] [--output=<path>] [--refresh]
```

| Argument | Effect |
|----------|--------|
| `[service-name]` | Names the service (drives the output slug and Service Overview). |
| `--type=<slug>` | One of the service-type profiles; unknown/omitted falls back to `generic`. |
| `--new` (default) | Interview → assemble from the profile → write. |
| `--update <source>` | Ingest an existing doc (file, path, Notion URL, or web URL) → interview only the gaps → rewrite. |
| `--brief` | Also produce the short-form Internal Service Brief (tiered Entry/Core/Premium). |
| `--output=<path>` | Override the default output location. |
| `--refresh` | Re-pull the module templates from Notion first (confirmation-gated). |

**Service types:** `consulting`, `ai-engineering`, `software-development`, `web-design`,
`ai-ppc-optimisation`, `branding`, `generic`.

**Interview-first:** the skill never writes an outline before completing the interview. It
confirms two addendum triggers — sensitive data / system integration (module 8) and AI/LLM
systems (module 9).

**Output (default):**

- `.project/business-development/service-outlines/<service-slug>/service-outline.md`
- `.project/business-development/service-outlines/<service-slug>/internal-service-brief.md` (with `--brief`)

## Structure

```text
business-development/
  .claude-plugin/plugin.json      # Claude Code manifest
  .codex-plugin/plugin.json       # Codex manifest + interface
  references/                     # template structure, profiles, input adapters, interview guide, notion refresh
  schemas/service-type-profile.schema.json
  scripts/validate-service-outline.py
  skills/service-outline/
    SKILL.md
    templates/modules/01..10-*.md          # bundled 10-module template
    templates/internal-service-brief.template.md
    templates/service-types/*.yaml         # per-service-type profiles
    examples/ai-ppc-optimisation.service-outline.md
    evals/suite.yaml
```

## Validation

```bash
python scripts/validate-service-outline.py <generated-outline.md>
python ../scripts/johns-os-marketplace.py validate
```

## Runtime boundaries

- No bundled MCP servers. `--update` from a Notion URL and `--refresh` use the user's
  connected Notion MCP; other sources use `Read` / `WebFetch`.
- Output is local Markdown. Writing back to Notion (via `--refresh` or an explicit request)
  is a confirmation-gated, mutating action.
- Generated documents never contain secrets, credentials, or invented client facts (`[TBC]`).
