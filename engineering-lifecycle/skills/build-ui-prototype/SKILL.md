---
name: build-ui-prototype
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*), AskUserQuestion
description: Use when the user asks to build a UI prototype, clickable MVP, app shell, dashboard mock, product demo, or frontend proof-of-concept; to recreate a design from an image; to redesign an existing component; or to scaffold an app from requirements, UX flows, or an implementation plan.
argument-hint: "[--image-to-component|--component-redesign|--web-page-design|--clickable-prototype|--scaffold-app] [--<style>]"
---

# Build UI Prototype

## Trigger

Use when the user asks for a prototype, mock, demo, clickable flow, app shell, a
component built from a screenshot, or a redesign of existing UI.

## When To Use

- Product value or a user journey needs to be seen before it is built.
- Requirements, UX flows or a screen inventory exist and need a visual check.
- An existing component needs redesigning.

## When Not To Use

- Production implementation. Use `implement-feature-safely`.
- Defining reusable standards. Use `create-design-system`.
- Backend or data work.

## Step 0: State The Design Read

Before any code, say in one line what you are building and for whom:

> *Reading this as: `<page kind>` for `<audience>`, in a `<style>` language, using
> `<design system or preset>`.*

If the design read genuinely diverges, ask **one** question. If it can be inferred,
do not ask.

## Step 1: Resolve The Mode

| Flag | Behaviour |
| --- | --- |
| `--image-to-component` | Rebuild an attached image as a component. Describe the structure you see (layout, grid, type scale, spacing rhythm, states) before writing any markup, and name what you cannot determine from the image rather than inventing it. |
| `--component-redesign` | Audit first: read the existing component, list what it does, what it gets right, and what is actually wrong. Preserve behaviour, props and accessibility. Change appearance only. |
| `--web-page-design` | A full page composition: hero, sections, footer, real copy. |
| `--clickable-prototype` | Multi-screen navigable flow with local state. No real persistence. |
| `--scaffold-app` | App shell: routing, layout, navigation, empty states. Not features. |

No flag: infer the mode, state it, proceed.

## Step 2: Resolve The Design Language

Never invent a visual language when one exists.

1. **Look for a design system** in this order:
   - `.project/.engineering/initiatives/<id>/design-system/design-tokens.md`
   - repo token files: `tokens.ts`, `theme.json`, `tailwind.config.*`, `src/design-system/`
   - existing components under `src/components/ui/`, `resources/views/components/`
   - `context/stack.json` for the framework and styling approach
2. **If one exists, use it.** Do not introduce a second visual language into a
   codebase that already has one. Say which system you found.
3. **If none exists**, offer `create-design-system` first when the work is durable.
4. **If the user declines, or this is throwaway**, ask one style question and apply
   a preset from `references/design-styles/`:

   `--brutalist` `--minimalist` `--glassmorphism` `--neumorphism`
   `--material-design` `--flat-design` `--editorial` `--futuristic`

   Each preset has `style.md` (the rules and its specific failure modes) and
   `starter.html` (a self-contained, token-driven page). Read `style.md` before
   using the starter. Copy the `:root` token block into the project rather than
   linking to the reference folder.

## Step 3: Read The Anti-Slop Register

Read `references/anti-slop-register.md` before generating.

It is **not a ban list**. Every entry names the pattern, why it reads as
machine-made, **when it is legitimate**, and what to do instead. Check the override
condition before rejecting a pattern: if the brief genuinely calls for it, use it
deliberately and say why.

The register's sections 7 to 10 cover the specific failure modes of the eight
presets. If you picked a preset, read its section.

## Step 4: Scope

Build the smallest prototype that demonstrates the value. One complete journey
beats five partial screens. Write the scope statement before the code:

- Mode and style, and why.
- The user journey in one sentence.
- Screens included; screens excluded and why.
- What is mocked versus real.
- Known limitations and what productionising would need.

## Step 5: Build

- Match existing repo conventions: framework, styling, file layout, naming.
- Keep mock data in a clearly named fixture location, visibly separate from real
  data paths. Never present a mock integration as a real connection.
- Cover the states that make a demo credible: empty, loading, error, populated,
  and the permission variants that matter.
- Accessibility is not deferred to production: semantic elements, labelled
  controls, visible focus, 4.5:1 body contrast, 44px targets, keyboard reachable.
- Do not add dependencies unless the repo already uses them or the prototype
  genuinely cannot work without them.

## Step 6: Check

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/anti-slop-check.py" <files you wrote>
```

Findings are advisory. For each one, either fix it or state which override
condition applies. Then walk the register's pre-flight list.

Run the project's own checks (lint, typecheck, build) from `context/stack.json`.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/validate-artifact.py" <artifact paths>
```

## Outputs

Under `.project/.engineering/initiatives/<initiative-id>/prototype/`:

- `prototype-plan.md` — scope statement, mode, style, journey, inclusions
- `prototype-implementation-log.md` — what was built and where
- `prototype-qa-checklist.md` — states and accessibility checks covered
- `prototype-limitations.md` — what is mocked, what productionising needs

Plus the prototype source, in the repo's own conventional location.

## Safety Constraints

- Never present mocked behaviour as real.
- Never write real credentials, keys or production endpoints into a prototype.
- Do not modify production code paths, migrations or data.
- Do not introduce a second design language into a codebase that has one.
- State every assumption made about content, brand or data that was not given.

## Related Agents

- `frontend-engineer`
- `ux-flow-designer`
- `qa-test-strategist`
