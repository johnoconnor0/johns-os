# Claude extension decision tree

Use this file to decide whether to create a skill, plugin, planning document, or update.

## Decision flow

```mermaid
flowchart TD
    A[User asks to create or update] --> B{Existing archive or directory?}
    B -->|Yes| C[Inspect before asking questions]
    B -->|No| D{One repeatable workflow?}
    C --> E{Contains plugin manifest?}
    E -->|Yes| F[Update plugin]
    E -->|No| G{One SKILL.md?}
    G -->|Yes| H[Update standalone skill]
    G -->|No| I[Inventory and ask split vs plugin]
    D -->|Yes| J{Needs agents/hooks/MCP/LSP/monitors/dependencies?}
    D -->|No| K[Planning doc or plugin]
    J -->|No| L[Create focused skill]
    J -->|Yes| M[Create plugin with skills]
```

## Choose a skill when

- One workflow can be described in a compact `SKILL.md`.
- The user needs repeatable prompts, templates, references, or deterministic scripts.
- There is no need for plugin-level installation, multiple component types, or dependencies.

## Choose a plugin when

- Multiple skills should ship together.
- The workflow needs plugin agents, hooks, MCP servers, LSP servers, monitors, channels, settings, commands, or dependencies.
- The user wants an installable extension bundle.
- The workflow is an operating model rather than a single task.

## Choose planning only when

- The user asks for an architecture or roadmap.
- The required external systems are not available yet.
- The user needs approval before implementation.

## Ask a clarification only when

The missing answer changes the artefact structure, permissions, target environment, or output contract. Otherwise, proceed with stated assumptions.
