# johns-os

`johns-os` is a local plugin marketplace. It indexes installable or local plugins,
tracks their metadata, and provides deterministic commands for discovery and
validation.

## Marketplace

The marketplace catalog lives at:

```text
marketplace/catalog.json
```

Each plugin has a detailed marketplace record under:

```text
marketplace/plugins/
```

The first registered plugin is:

- `engineering-lifecycle`: a Claude Code plugin for structured product and engineering lifecycle work.

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
marketplace/
  catalog.json
  plugins/
    engineering-lifecycle.json
  schemas/
    catalog.schema.json
    plugin.schema.json
scripts/
  johns-os-marketplace.py
engineering-lifecycle/
  .claude-plugin/plugin.json
```
