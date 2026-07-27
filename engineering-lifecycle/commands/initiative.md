---
name: initiative
description: Create, switch, close, or list Engineering Lifecycle initiatives. An initiative is the folder every PRD, design, plan, review, and test artifact for one piece of work belongs to.
argument-hint: "[new|switch|close|list] [<id>] [--title \"...\"]"
allowed-tools: Bash, AskUserQuestion, Read
---

# Initiative

An initiative is one coherent piece of work: a feature, a migration, a refactor.
Every lifecycle artifact lives under `.project/.engineering/initiatives/<id>/<stage>/`.

Exactly one initiative is **active** at a time. New artifacts belong to it. This
command is how that pointer moves; nothing else should move it silently.

## Why this exists

Initiatives used to come into existence as a side effect: the first skill to write
an artifact invented a folder name, and nothing recorded it. A session that started
on one initiative and pivoted to unrelated work kept writing into the original
folder, because nothing was watching. The result was a PRD for one feature buried
inside another feature's directory.

The registry (`initiatives/registry.json`) and the `UserPromptSubmit` drift check
close that gap. This command is the human-facing half.

## Actions

| Action | Effect |
| --- | --- |
| `list` (default) | Show every initiative, its status, and which is active. |
| `new <id>` | Create the folder with all lifecycle stages, register it, make it active. |
| `switch <id>` | Move the active pointer to an existing initiative. |
| `close [<id>]` | Mark it closed. Defaults to the active one. |

## Flow

1. **Parse `$ARGUMENTS`** for the action and id. With no argument, run `list`.
2. **For `new`:** derive a slug from the id or title. Prefer a short noun phrase
   naming the work (`billing-exports`, `oauth-migration`), not a date or a ticket
   number alone. If a similar initiative already exists, use `AskUserQuestion` to
   confirm the user wants a separate one rather than continuing in it.
3. **Run the command:**

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/initiative.py" --action list
   ```

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/initiative.py" --action new --id billing-exports --text "Billing exports"
   ```

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/initiative.py" --action switch --id billing-exports
   ```

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/initiative.py" --action close --id billing-exports
   ```

4. **Report** the active initiative and, for `new`, the stage folders created.

## Behavioural Rules

1. **Never invent an initiative silently.** If lifecycle work is requested and the
   prompt does not clearly belong to the active initiative, ask before writing.
   The intake hook flags this; do not ignore it.
2. **One active initiative.** Switching is explicit. Writing into a non-active
   initiative prompts for confirmation via the edit-scope guard.
3. **Closing is not deleting.** A closed initiative keeps every artifact; it just
   stops being a default target.
4. **The registry follows the filesystem.** A folder created by hand is adopted on
   the next read rather than ignored, so the two can never disagree.

## Outputs

- `.project/.engineering/initiatives/registry.json`
- `.project/.engineering/initiatives/<id>/<stage>/` for all 14 lifecycle stages
