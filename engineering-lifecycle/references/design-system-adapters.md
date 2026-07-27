# Design System Adapters

A design system is a set of decisions (scale, palette, spacing, states,
accessibility rules) plus an implementation of those decisions in one stack. The
decisions are portable; the implementation is not.

The adapter is the second half. Everything before it — principles, foundations,
tokens, component inventory, state rules — is written once and is stack-neutral.

## Choosing

Read `context/stack.json`, which `detect-stack.py` populates with evidence.

| Detected | Adapter |
| --- | --- |
| React + Tailwind | `react-tailwind` |
| React, no Tailwind | `react-css` |
| Vue or Nuxt | `vue-nuxt` |
| PHP with `composer.json`, no framework | `php-native` |
| WordPress (`wp-content`, `theme.json`) | `wordpress` |
| Laravel (`laravel/framework`) | `laravel-blade` |
| No JS framework, static HTML | `static-html` |

Override with `--adapter=<name>` when detection is wrong, or when the target stack
does not exist yet. State which adapter you chose and the evidence for it.

## The token contract

Every adapter expresses the same semantic tokens. Only the syntax and file
locations change.

```
colour     bg, surface, surface-2, fg, fg-muted, accent, accent-fg, border,
           success, warning, danger
type       font-display, font-body, font-mono, and a size scale
space      one base unit, all spacing a multiple of it
shape      radius scale, border widths
depth      shadow scale
motion     duration-fast, duration-slow, easing
breakpoint sm 640, md 768, lg 1024, xl 1280, 2xl 1536
```

**CSS custom properties are the lowest common denominator** and every adapter
below emits them. A framework-native layer sits on top where one exists. That way
a component written for one adapter can be ported by changing the wrapper, not the
values.

---

## react-tailwind

- **Tokens:** `src/design-system/tokens.ts` exporting a typed object, plus CSS
  custom properties in the global stylesheet. Tailwind v4 reads them through
  `@theme`; Tailwind v3 through `theme.extend` in `tailwind.config.ts`.
- **Components:** `src/components/ui/`. If shadcn/ui is present, own the generated
  code and restyle it — never ship it in its default state, which is recognisable.
- **Dark mode:** the `dark:` variant driven by a `class` or `data-theme` strategy.
- **Note:** Tailwind v4 uses `@tailwindcss/postcss` or the Vite plugin, not the
  `tailwindcss` PostCSS plugin.

## react-css

- **Tokens:** `src/design-system/tokens.css` as custom properties, plus a
  `tokens.ts` mirror for values needed in JS.
- **Components:** CSS Modules (`Button.module.css`) beside each component.
- **Dark mode:** `prefers-color-scheme` plus a `:root[data-theme]` override so a
  toggle can win.

## vue-nuxt

- **Tokens:** `assets/css/tokens.css`, referenced from `nuxt.config.ts` `css`.
- **Components:** `components/ui/`, auto-imported by Nuxt.
- **Dark mode:** `@nuxtjs/color-mode` if present, otherwise the same
  `data-theme` pattern.

## php-native

- **Tokens:** `assets/css/tokens.css` as custom properties. No build step.
- **Components:** `templates/components/*.php`, each a partial taking an
  associative array of props:

  ```php
  <?php /* templates/components/button.php */
  $variant = $variant ?? 'primary';
  $label   = $label ?? 'Submit';
  ?>
  <button class="btn btn--<?= htmlspecialchars($variant) ?>">
    <?= htmlspecialchars($label) ?>
  </button>
  ```

- **Rule:** escape on output. A component that interpolates unescaped props is a
  cross-site scripting hole shipped once and reused everywhere.
- **Include:** a small `component()` helper beats bare `include` because it scopes
  the props.

## wordpress

- **Tokens:** `theme.json` is authoritative. Its `settings.color.palette`,
  `settings.typography.fontSizes` and `settings.spacing.spacingSizes` generate CSS
  custom properties automatically and populate the editor UI, which is the point:
  tokens defined anywhere else are invisible to editors.
- **Components:** block patterns in `patterns/`, template parts in `parts/`.
- **Styles:** `style.css` for anything `theme.json` cannot express.
- **Rule:** do not hardcode hex values in block markup. An editor changing the
  palette must change the site.

## laravel-blade

- **Tokens:** `resources/css/tokens.css`, imported by the app stylesheet. Tailwind
  is conventional here; if present, use the `react-tailwind` token approach.
- **Components:** `resources/views/components/*.blade.php` as anonymous
  components, used as `<x-button variant="primary">`.
- **Props:** declare with `@props([...])` so defaults are explicit.
- **Rule:** `{{ }}` escapes, `{!! !!}` does not. Components take escaped content.

## static-html

- **Tokens:** `css/tokens.css`.
- **Components:** HTML partials plus a documented class contract, since there is
  no component runtime to enforce it.
- **Rule:** with no framework preventing drift, the component inventory document
  is the only enforcement. Keep it accurate or the system decays.

---

## Rules for every adapter

1. **Semantic names, not literal ones.** `--accent`, not `--blue-500`. A literal
   name has to be renamed when the brand changes; a semantic one does not.
2. **One system per project.** Never mix Material and shadcn, or Carbon and
   Tailwind, in one tree.
3. **Accessibility rules are part of the system, not a later pass**: 4.5:1 body
   contrast, 44px targets (48px for Material), visible focus, and a documented
   state for every interactive component.
4. **Every component documents its states**: default, hover, focus, active,
   disabled, loading, error, empty. A component inventory without states is a list
   of names.
5. **Never invent brand rules.** Colours, fonts and logos come from the user or
   from existing code. Separate "inspected and confirmed" from "proposed".
