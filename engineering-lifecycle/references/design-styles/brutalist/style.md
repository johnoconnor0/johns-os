# Brutalist

Raw, intentionally unpolished. Bold typography, sharp contrast, visible structure,
unconventional layout. Derived from Swiss typographic print and terminal interfaces.

Brutalism is not "unstyled". It is rigorously gridded and typographically precise.
Every raw edge is deliberate. Careless output is not brutalist, it is unfinished.

## Type

- **Display:** heavy neo-grotesque. Archivo Black, Inter Black, Helvetica Bold.
  Fluid scale via `clamp(3rem, 9vw, 11rem)`. Tracking tight to negative
  (`-0.03em`). Leading compressed (`0.9`). Uppercase.
- **Data and metadata:** monospace. Small (`0.7rem` to `0.875rem`), generous
  tracking (`0.08em`), uppercase.
- Type is the primary structure. Imagery is secondary.

## Colour

Pick one substrate and commit. Never mix the two within a page.

- **Print:** background `#F4F4F0`, foreground `#0A0A0A`, accent `#E61919`.
- **Terminal:** background `#0A0A0A`, foreground `#EAEAEA`, accent `#E61919`.

One accent only, used for rules, emphasis and alerts. No gradients, no soft
shadows, no translucency.

## Shape and layout

- `border-radius: 0`. Every corner is 90 degrees.
- Visible compartmentalisation: `1px` and `2px` solid borders delineating zones.
- Grid gap trick: `display: grid; gap: 1px` with a contrasting parent background
  produces hairline rules without per-element borders.
- Bimodal density: dense monospace metadata against large empty regions.

## Motion

Minimal. Instant state changes, no easing curves that suggest softness. If motion
is used at all it is a hard cut or a linear translate.

## Failure modes

- **"Unstyled" as an excuse.** If the grid is not exact and the type scale is not
  deliberate, it reads as broken rather than raw.
- **Decoration masquerading as structure.** ASCII brackets, crosshairs and
  registration marks are only legitimate when they mark something real.
- **Contrast without hierarchy.** Everything shouting is the same as nothing
  shouting. Vary scale by an order of magnitude, not by 20 percent.
- **Accessibility.** Uppercase monospace at `0.7rem` is hard to read. Keep body
  copy in sentence case at a normal size; reserve the extremes for headings and
  short labels.
