# Design Style Presets

Starting points for `build-ui-prototype` when no design system exists and the user
does not want to build one first.

Each style is a folder with two files:

- `style.md` — the rules: type, colour, spacing, shape, motion, and what this style
  gets wrong when applied carelessly.
- `starter.html` — a self-contained page. No build step, no external requests,
  CSS custom properties throughout, light and dark, `prefers-reduced-motion`
  honoured. Open it in a browser, or copy the `:root` block into an existing
  project as a token set.

## Available

| Flag | Style |
| --- | --- |
| `--brutalist` | Raw, unpolished, bold type, sharp contrast, visible grid |
| `--minimalist` | Generous whitespace, limited palette, essential elements only |
| `--glassmorphism` | Translucent panels, blurred backdrops, layered depth |
| `--neumorphism` | Soft extruded surfaces from paired light and dark shadows |
| `--material-design` | Structured grids, elevation, motion, familiar components |
| `--flat-design` | Two-dimensional, no texture or gradient, colour carries affordance |
| `--editorial` | Magazine layout, expressive type, asymmetric grid |
| `--futuristic` | Dark, neon accents, technical type, data-dense |

## The Token Contract

Every starter defines the same custom properties, so a prototype can be moved from
one style to another by swapping the `:root` block. Component markup does not
change; only the tokens do.

```
--bg            page background          --fg            primary text
--surface       raised surface           --fg-muted      secondary text
--surface-2     second layer             --accent        the single accent
--border        divider / outline        --accent-fg     text on accent
--radius        corner radius            --shadow        elevation
--font-display  headings                 --font-body     body
--font-mono     code and data            --space         base spacing unit
--motion-fast   micro-interactions       --motion-slow   entrances
```

## Rules For Every Style

1. **One accent colour**, used consistently across the whole page.
2. **Light and dark both work.** `prefers-color-scheme` plus a `data-theme`
   override so a toggle can win.
3. **Body text meets 4.5:1**, interactive targets at least 44px, visible focus
   rings. Neumorphism has an explicit exception recorded in its `style.md`.
4. **`prefers-reduced-motion` disables non-essential animation.**
5. **Nothing external.** No CDN, no web font request, no remote image. System font
   stacks and `picsum.photos` placeholders only where images are genuinely needed.
6. **Check `references/anti-slop-register.md`** before presenting. The register's
   sections 7 to 10 cover the specific failure modes of these styles.
