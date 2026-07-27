# Minimalist

Clean layouts, generous whitespace, a limited palette, and only the interface
elements the task actually needs.

Reduction is not absence. Every element that survives must be load-bearing. A page
that is empty because the work was not done is not minimalist, it is unfinished.

## Type

- **Display:** a single sans family at two or three weights. Geist, Inter Tight,
  Cabinet Grotesk. `clamp(2rem, 4vw, 3.5rem)`, tracking `-0.02em`, leading `1.1`.
- **Body:** same family, `1rem` to `1.0625rem`, leading `1.6`, measure capped at
  65 characters.
- Hierarchy comes from weight and colour, not size. Two sizes and two weights are
  usually enough for a whole page.

## Colour

- Background near-white (`#FAFAF9`) or near-black in dark mode. Never pure white
  or pure black.
- Three greys: primary text, muted text, border. That is the whole neutral scale.
- One accent, used sparingly enough that it still means something. If the accent
  appears more than a handful of times per screen it has stopped being an accent.

## Space

Whitespace is the composition tool, so it must be systematic.

- One base unit (8px), all spacing a multiple of it.
- Section padding is large: `96px` to `128px` vertical on desktop.
- The gap between related items must be visibly smaller than the gap between
  groups. Proximity is doing the grouping work that borders would otherwise do.

## Shape and depth

- Small consistent radius (`6px` to `10px`) or none at all. Pick one.
- Borders over shadows. Where a shadow is needed, keep it near-invisible
  (`0 1px 2px rgba(0,0,0,0.04)`).

## Motion

Invisible but present. Entrances at `translateY(8px)` and `opacity: 0` resolving
over `500ms` with `cubic-bezier(0.16, 1, 0.3, 1)`. Hover changes colour, not size.

## Failure modes

- **Empty rather than reduced.** If a section says nothing, deleting it is
  minimalist. Making it beautiful and still empty is not.
- **Low contrast mistaken for restraint.** Muted text still needs 4.5:1.
- **Affordance stripped along with decoration.** A button with no border, no fill
  and no shadow is not a button. Keep one clear affordance.
- **Inconsistent spacing.** With no borders or colour to hide behind, a 14px gap
  next to a 16px gap is immediately visible.
