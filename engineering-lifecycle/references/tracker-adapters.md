_Adding an issue tracker, and what an adapter has to answer._

# Tracker Adapters

`scripts/trackers.py` holds one frozen `Tracker` per provider, the same shape
`dialects.py` uses for database engines and `references/design-system-adapters.md`
describes for frontend stacks. Four ship: `linear`, `github`, `jira`, and `file`.

`file` is the default. It files nowhere — issues stay in the local queue and its
generated digest — which is what makes surfacing work in a project that has never
configured a tracker.

## What an adapter carries

| Field | Answers |
| --- | --- |
| `create_tool`, `update_tool`, `search_tool`, `get_tool`, `comment_tool` | The **bare verbs**. Never a full `mcp__...` name — see below |
| `server_candidates` | Server segments worth trying when config names none |
| `field_map` | Canonical field → this provider's argument name. Linear calls the body `description`; Jira calls the title `summary` |
| `scope_map` | Config scope key → argument name. `team`/`project` for Linear, `owner`/`repo` for GitHub |
| `update_key` | The argument carrying an existing id. For Linear its presence is what turns a create into an update |
| `id_key`, `url_key`, `identifier_key` | Where the created issue's identifiers appear in the tool's response |
| `priority_map` | Local severity → the provider's scale. Empty for GitHub, which has no priority field |
| `default_status_map` | Local status → workflow state name |
| `url_patterns` | How a pasted URL decodes into scope ids |

## Why tool names are stored as bare verbs

A tracker reached through MCP is addressed as `mcp__<server>__<verb>`. The server
segment is not a property of the tracker — it is a property of how *this machine*
connected to it. A workspace connector gets a UUID. A `.mcp.json` declaration gets
the name it was declared under. Same Linear, two different tool names, and a repo
can have both configured at once.

So the provider declares `save_issue` and the server comes from
`settings.json` `mcp_server`. When that is unset, `tool_candidates` lists every
plausible spelling and the model uses whichever resolves. Hooks cannot see which MCP
servers are connected, so the first attempt is necessarily a guess — `reconcile`
records the one that worked, and the guess happens once per repository rather than
once per run.

## Adding a provider without touching any code

Drop a JSON file in `.project/.engineering/tracker/providers/<name>.json`. Every
field above is data, so a descriptor is enough:

```json
{
  "name": "shortcut",
  "label": "Shortcut",
  "extends": "linear",
  "create_tool": "create_story",
  "update_tool": "update_story",
  "server_candidates": ["shortcut"],
  "field_map": { "title": "name", "body": "description" },
  "scope_map": { "project": "project_id" },
  "update_key": "story_id",
  "id_key": "id",
  "url_key": "app_url"
}
```

`extends` starts from a built-in and overrides only what differs.

**When code is needed instead:** a provider whose *call shape* differs — one needing
two calls to create an issue, or a paginated search before every create — cannot be
expressed as data and should get a built-in entry in `trackers.py`. Everything else
should not require a code change, and if it does, that is a gap in the dataclass
rather than a reason to special-case the provider.

## What stays shared

The queue, the stable ids, the content hashing, the plan/reconcile round trip, the
digest, the settings resolution and the kill switch are provider-independent. An
adapter never sees the queue and never decides whether something should be filed —
only how to say it in that tracker's vocabulary.
