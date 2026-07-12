# Validation and packaging checklist

## Static validation

Run the bundled validator:

```bash
python3 scripts/check_claude_extension.py <path-to-skill-or-plugin>
```

It checks common structural mistakes but does not replace official Claude validation.

## Official validation

When available, run:

```bash
claude plugin validate <plugin-path>
```

Record whether it passed, failed, or was unavailable.

## Skill checks

- `SKILL.md` exists and is uppercase.
- YAML frontmatter parses.
- `name` exists and is kebab-case.
- `description` exists and includes trigger context.
- `SKILL.md` is under 500 lines or has an explicit reason.
- `$ARGUMENTS` is used when `argument-hint` exists.
- Directly referenced files exist.
- Templates and examples contain no TODO placeholders.

## Plugin checks

- `.claude-plugin/plugin.json` exists.
- JSON parses.
- Component paths exist.
- Component directories are at plugin root.
- Skills have valid `SKILL.md` files.
- Agent files have valid frontmatter.
- Hook configs and scripts exist.
- MCP/LSP JSON files parse when present.
- Version uses semantic versioning.

## Script checks

- Scripts have a clear purpose.
- Scripts do not require undeclared dependencies.
- Representative scripts were run.
- Scripts avoid destructive defaults.

## Package checks

- Zip contains the extension root directory.
- No `.git`, `node_modules`, cache, temp, secret, credential, or private data files.
- Package size is acceptable for the target upload flow.
- Final response links the zip and summarises validation performed.
