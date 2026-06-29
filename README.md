# johns-os

`johns-os` is a Claude Code plugin marketplace. It indexes installable plugins,
tracks their metadata, and provides deterministic commands for discovery and
validation. It also carries parallel Codex marketplace metadata.

The first registered plugin is:

- `engineering-lifecycle`: a Claude Code plugin for structured product and engineering lifecycle work (19 skills, 19 agents, lifecycle hooks).

## Install (Claude Code)

The authoritative Claude Code marketplace manifest lives at
`.claude-plugin/marketplace.json`. Add the marketplace and install a plugin:

```text
/plugin marketplace add johnoconnor0/johns-os
/plugin install engineering-lifecycle@johns-os
```

For local development against a clone, point the marketplace at the path:

```text
/plugin marketplace add ./johns-os
```

Update later with:

```text
/plugin marketplace update johns-os
```

## Marketplace metadata

| File | Consumer |
|------|----------|
| `.claude-plugin/marketplace.json` | Claude Code (authoritative) |
| `marketplace.json`, `.agents/plugins/marketplace.json` | Codex |
| `marketplace/catalog.json`, `marketplace/plugins/` | `scripts/johns-os-marketplace.py` (discovery/validation) |

## Commands

List marketplace plugins:

```powershell
python scripts/johns-os-marketplace.py list
```

Search plugins:

```powershell
python scripts/johns-os-marketplace.py search lifecycle
```

Show one plugin:

```powershell
python scripts/johns-os-marketplace.py show engineering-lifecycle
```

Validate marketplace records and local plugin manifests:

```powershell
python scripts/johns-os-marketplace.py validate
```

## Layout

```text
.claude-plugin/
  marketplace.json          # Claude Code marketplace manifest (authoritative)
marketplace.json            # Codex marketplace manifest
marketplace/
  catalog.json
  plugins/
    engineering-lifecycle.json
  schemas/
    catalog.schema.json
    plugin.schema.json
.agents/
  plugins/
    marketplace.json        # Codex marketplace manifest
scripts/
  johns-os-marketplace.py
engineering-lifecycle/
  .claude-plugin/plugin.json
  .codex-plugin/plugin.json
```
