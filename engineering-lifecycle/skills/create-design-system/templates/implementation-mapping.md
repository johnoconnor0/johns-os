---
initiative_id: example-initiative
skill: create-design-system
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - design-system-plan.md
  - design-tokens.md
  - component-inventory.md
---

# Design System Implementation Mapping

## Adapter

- Adapter chosen:
- Evidence (from `context/stack.json` or inspected files):
- Overridden with `--adapter`: yes / no, and why

See `references/design-system-adapters.md` for this adapter's conventions.

## Current Stack

- Framework:
- Styling:
- Component library:
- Existing component path:
- Existing token/theme path:
- Existing conventions confirmed by inspection (as opposed to proposed):

## Recommended File Structure

Replace with the structure for the chosen adapter. Examples:

```text
# react-tailwind
src/design-system/tokens.ts        src/components/ui/

# php-native
assets/css/tokens.css              templates/components/*.php

# wordpress
theme.json                         patterns/  parts/

# laravel-blade
resources/css/tokens.css           resources/views/components/*.blade.php
```

## Token Mapping

Every adapter emits CSS custom properties. The framework-native column is the
layer on top, and is empty for adapters that have none.

| Token Category | CSS Custom Property | Framework-Native Location | Notes |
| --- | --- | --- | --- |
| Colour | `--bg`, `--fg`, `--accent`, ... | | |
| Spacing | `--space` and multiples | | |
| Typography | `--font-display`, `--font-body` | | |
| Shape | `--radius` scale | | |
| Depth | `--shadow` scale | | |
| Motion | `--motion-fast`, `--motion-slow` | | |

## Component Mapping

| Component | Implementation Path | Source / Dependency | States Covered | Notes |
| --- | --- | --- | --- | --- |
| Button | | existing / new | default, hover, focus, active, disabled, loading | |

## Escaping And Safety

For template-based adapters (`php-native`, `laravel-blade`, `wordpress`), record
how props are escaped on output. A component that interpolates unescaped input is
a cross-site scripting hole written once and reused everywhere.

- Escaping mechanism:
- Components taking raw HTML (and why):

## Prototype Usage

- Components needed for `build-ui-prototype`:
- Mock-data considerations:
- Layout considerations:

## Productionisation Notes

- Tests required:
- Accessibility checks:
- Docs / Storybook / pattern library:
- Review gates:

## Open Questions

- [ ] Question:
