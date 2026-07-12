# Example Skill Build: release-notes-writer

## What I built

A focused Claude Code skill that turns merged PRs and commit history into customer-facing release notes.

## Structure

```text
release-notes-writer/
  SKILL.md
  templates/output-template.md
  examples/example-output.md
  references/style-guide.md
  LICENSE.txt
```

## Key behaviours

- Reads `$ARGUMENTS` for release range and target audience.
- Uses `git log` only when the repository is available.
- Separates customer-facing changes from internal maintenance.
- Produces markdown and optional JSON summary.

## Validation

- Static validator passed.
- Official Claude validation was unavailable in this environment.
