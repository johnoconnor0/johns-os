# johns-os

Install and manage the [johns-os](https://github.com/johnoconnor0/johns-os) Claude
Code plugin marketplace.

```bash
npx johns-os install
```

Adds the marketplace and installs all three plugins:

| Plugin | What it does |
| --- | --- |
| `engineering-lifecycle` | Discovery, requirements, technical design, data model, API contracts, engineering plans, review, testing, release and repo hygiene, with deterministic local artifacts |
| `business-development` | Service Outline documents from a modular, service-type-aware template |
| `ai-utilities` | Author, review and audit Claude Code extensions and plans |

Restart Claude Code afterwards to load them.

## Commands

```bash
npx johns-os list                        # what is available and what is installed
npx johns-os install engineering-lifecycle
npx johns-os install --scope project     # user (default), project, or local
npx johns-os update                      # refresh the marketplace, update plugins
npx johns-os init                        # create the lifecycle workspace in this repo
npx johns-os doctor                      # where the running copy came from, and how stale
```

## Why `doctor` exists

Claude Code does not run a plugin from a working tree. It installs a
version-pinned copy under `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`,
and because this marketplace is a git source, updates are fetched from the remote.

The consequence is easy to miss: a local checkout can be many commits ahead of the
copy that is actually executing, with no symptom other than edits appearing to do
nothing. `doctor` prints the install path, the pinned commit and any version
mismatch, so that gap is visible rather than inferred.

Requires the [Claude Code CLI](https://claude.com/claude-code) on `PATH`, and
Node 18 or newer. No dependencies.

MIT licensed.
