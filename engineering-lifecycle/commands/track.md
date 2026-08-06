---
name: track
description: File surfaced issues into the configured issue tracker, or configure issue tracking for this project.
argument-hint: "[status|plan|file|add \"<title>\"|init|on|off]"
allowed-tools: Bash, Read, AskUserQuestion
---

# Track

Issues surfaced during a session go into a local queue. This command is how they
reach the tracker, and how tracking gets configured in the first place.

There is deliberately **no MCP tool in `allowed-tools`**. The tool name depends on
how this machine connected to the tracker — a workspace connector gets a UUID, a
`.mcp.json` declaration gets its declared name — so hardcoding one would break the
other. The normal permission prompt applies on first use.

## Actions

| Action | Effect |
| --- | --- |
| `status` (default) | Counts: queued, filed, and how many sit below the severity threshold |
| `add "<title>"` | Record one issue into the queue |
| `plan` | Emit the operations to execute through the tracker's MCP tools |
| `file` | `plan`, execute it, then `reconcile` — the full round trip |
| `init` | Write a starter `settings.json`, then walk through configuring it |
| `on` / `off` | The kill switch |

## Configuration

`.project/.engineering/settings.json` — the one hand-authored, committed file under
that tree. Everything else there is regenerable.

```json
{
  "version": 1,
  "issue_filing": {
    "enabled": true,
    "provider": "linear",
    "mcp_server": "<the server segment of your MCP tool names>",
    "scope": { "team": "<team>", "project": null },
    "dispatch": { "on_stop": true, "min_severity": "medium" },
    "labels": ["eng-lifecycle"]
  }
}
```

Any of it can be overridden per session by environment variables:
`ISSUE_MANAGEMENT_SOFTWARE`, `ENABLE_ISSUE_FILING`, `LINEAR_PROJECT_ID`,
`LINEAR_PROJECT_URL`, `LINEAR_TEAM_ID`, `ISSUE_TRACKER_MCP_SERVER`.

## Filing, step by step

1. **Get the plan.**

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/surface-issue.py" --root . plan --include-ledger
   ```

   If it returns `configured: false`, stop and report why — `provider_reason` says.
   Nothing is wrong with an unconfigured project; issues stay in the local queue.

2. **Execute each operation.** Every operation carries a resolved `tool` and a
   `tool_candidates` list. Use `tool` if it exists; otherwise try the candidates.
   Hooks cannot see which MCP servers are connected, so the first attempt in a new
   environment is a guess — that is expected, and it self-corrects.

3. **Reconcile.** Write `[{key, id, url, identifier}]` to a file and:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/surface-issue.py" --root . reconcile \
     --results <file> --mcp-server <the server segment that worked>
   ```

   Passing `--mcp-server` is what makes the guess in step 2 happen once per
   repository rather than once per run.

4. **Confirm.** Re-run `plan`. It must return zero operations.

## Safety Constraints

- **Never file an issue the user has not seen.** Filing is outward-facing: list what
  is about to be created and confirm before the first create in a session.
- **Do not invent scope.** If `team` or `project` is missing, ask. Filing into the
  wrong team is worse than not filing.
- **Do not delete anything in the tracker.** `resolve` marks the local queue entry;
  closing the real issue is the user's call.
- If `settings.json` is malformed, `off` still works — the sentinel is checked
  before any JSON is parsed.
