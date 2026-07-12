# Claude Code skill design guide

## Required structure

```text
<skill-name>/
  SKILL.md
  references/      # optional; directly linked from SKILL.md
  templates/       # optional reusable output skeletons
  examples/        # optional realistic examples
  scripts/         # optional deterministic helpers
  evals/           # optional tests/evaluation notes
  LICENSE.txt      # recommended
```

## SKILL.md frontmatter

Use concise, trigger-rich frontmatter. Keep the `description` specific because it is the activation surface.

```yaml
---
name: example-skill
description: Do a specific repeatable workflow. Use when the user asks for concrete triggers and outputs.
argument-hint: "[input] [--option]"
allowed-tools: "Read, Write, Grep, Glob"
effort: medium
---
```

## Body pattern

1. User context with `$ARGUMENTS`.
2. Mission/role.
3. Phases or workflow.
4. Output format.
5. Behavioural rules.
6. Edge cases.
7. Links to references/templates/examples.

## Progressive loading

- Keep operational instructions in `SKILL.md`.
- Move dense frameworks, schemas, lookup tables, examples, long checklists, and stack-specific adapters to `references/`.
- Keep reference files directly linked from `SKILL.md`.
- Keep long reference files organised with headings and short tables.

## Tool permissions

Grant the narrowest useful tool set. Examples:

| Skill type | Typical tools |
|---|---|
| Writing/template skill | `Read, Write, Edit` |
| Codebase analysis | `Read, Grep, Glob, Bash`, optionally `Agent` |
| File transformation | `Read, Write, Bash(python3:*)` |
| Plugin scaffolding | `Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(zip:*), Bash(python3:*)` |

## Common mistakes

- Putting all reference material into `SKILL.md`.
- Hiding trigger criteria only in the body instead of the description.
- Creating scripts that duplicate model reasoning rather than deterministic work.
- Shipping placeholder examples.
- Over-granting tools such as unrestricted Bash.
- Returning only modified files when the user asked for a complete updated package.
