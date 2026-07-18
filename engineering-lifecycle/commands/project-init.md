---
name: project-init
description: Initialize the Engineering Lifecycle workspace (.project/.engineering) for this repo. Creates it at the repo root by default, or in the current subfolder with `here`.
argument-hint: "[here]"
allowed-tools: Bash, AskUserQuestion
---

# Project Init

Explicitly create the Engineering Lifecycle workspace. This is the **only** way the
workspace is meant to be created — the plugin never auto-generates `.project`. Use it
when a session-start prompt offered to initialize, or any time you want lifecycle
skills and hooks active for a repo.

## Where it goes

- **Default (no argument):** the workspace is created at the **repo root** (the nearest
  ancestor containing `.git` or `.claude-plugin/plugin.json`). This is correct almost
  every time — `.project` belongs at the repo root.
- **`here` (or `.`):** the workspace is created in the **current working directory
  exactly**, without walking up. Use this deliberately for a nested package, e.g. running
  it from `plugins/web-lifter-cloud` to get `plugins/web-lifter-cloud/.project`.

## Flow

1. **Resolve target.** Inspect `$ARGUMENTS`:
   - If it contains `here` or `.` → subfolder mode (`--here`), target = current directory.
   - Otherwise → repo-root mode, target = the resolved repo root.
2. **Confirm only when ambiguous.** If subfolder mode is requested but the current
   directory *is* the repo root, or if a `.project/.engineering` already exists at a
   different level, use `AskUserQuestion` to confirm the intended location before writing.
   Otherwise proceed — this command is the user's explicit opt-in.
3. **Initialize** by running the workspace initializer:

   ```bash
   # Repo-root mode (default)
   python "${CLAUDE_PLUGIN_ROOT}/scripts/init-workspace.py"

   # Subfolder mode (`/project-init here` from the target directory)
   python "${CLAUDE_PLUGIN_ROOT}/scripts/init-workspace.py" --here
   ```

   The initializer is idempotent (`exist_ok=True`): re-running it never clobbers existing
   artifacts, it only ensures the directory scaffold and `workspace.json` manifest exist.
4. **Populate stack context** (best-effort, so `stack.json` exists for later skills):

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/detect-stack.py"
   ```
5. **Report** the created location and confirm the plugin is now active for this repo.

## Behavioural Rules

1. **Never create `.project` outside the resolved target.** Repo root by default; the
   current directory only when `here` is explicitly requested.
2. **Idempotent.** Safe to run repeatedly; it will not overwrite existing lifecycle
   artifacts.
3. **No version control.** This command does not stage, commit, or push. `.project/` is
   gitignored by the plugin's hygiene rules and is not meant to be tracked.

## Final Message

After initializing, print:

> *Engineering Lifecycle workspace initialized at `<location>/.project/.engineering`.*
> *Lifecycle skills and hooks are now active for this repo.*
> *Next: run `profile-product-system` to map the product, or `map-product-lifecycle` to see what artifacts are missing.*
