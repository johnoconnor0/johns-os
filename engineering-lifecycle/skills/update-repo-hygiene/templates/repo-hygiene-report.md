---
initiative_id: repo-hygiene
skill: update-repo-hygiene
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - hygiene-report.json
---

# Repository Hygiene Report

## Environment Variables

| Variable | Seen In | In `.env.example` | Recommended Placeholder |
| --- | --- | --- | --- |
| NAME | file | yes/no | NAME=example |

## Gitignore Candidates

| Pattern | Reason | Safe To Add |
| --- | --- | --- |
| pattern | generated/local-only reason | yes/no |

## Support File Updates

| File | Reason | Auto-Edit Safe? |
| --- | --- | --- |
| README.md / CHANGELOG.md / CLAUDE.md / config | Drift or missing doc | yes/no |

## Risks

| Risk | Impact | Manual Decision |
| --- | --- | --- |
| Risk | Impact | Decision needed |

## Applied Changes

Record support-file edits that were explicitly requested and safely applied.
