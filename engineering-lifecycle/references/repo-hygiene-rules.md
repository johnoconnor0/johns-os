# Repository Hygiene Rules

Repo hygiene is a two-tier system: automatic detection and controlled update.

## Automatic Detection

Hooks and scripts may detect:

- new untracked files,
- generated build outputs,
- local databases and logs,
- environment variables introduced in code,
- secret-like variable names,
- new config files,
- new ports or package scripts,
- new service dependencies.

Detection writes reports under `.project/.engineering/hygiene/` and should normally exit zero.

## Controlled Updates

Automatic edits are limited to support files and only when explicitly requested:

- `.env.example`
- `.gitignore`
- `.dockerignore`
- `README.md`
- `CHANGELOG.md`
- `CLAUDE.md`

Rules:

- `.env.example` may contain variable names and placeholders only.
- Never copy secret values from local env files.
- `.gitignore` additions must be known generated or local-only patterns.
- Do not ignore source directories or lockfiles unless project policy explicitly says so.
- README and CHANGELOG edits are suggested by default.
- CLAUDE.md should contain durable project conventions, not transient task notes.

## Hygiene Report

Every hygiene pass should refresh:

- `.project/.engineering/hygiene/hygiene-report.json`
- `.project/.engineering/hygiene/hygiene-report.md`
