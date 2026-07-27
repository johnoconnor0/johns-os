# Futuristic

Dark interfaces, neon accents, glowing elements, technical typography, data
visualisation, animated effects.

## The trap

This is the easiest style to make unreadable and slow. Neon on black with a glow
on every element is both the default reach and the worst version of it.

The discipline: **the glow is a highlight, not a texture.** One or two elements
per view glow. Everything else is legible dark-mode UI.

## Colour

- Background: near-black with a hue, not `#000000`. `#08090F`, `#0A0E14`.
  Layered surfaces step up in lightness, not in hue.
- **One neon accent.** Cyan, electric green, magenta, amber. Not three.
- Semantic colours for data states must remain distinguishable when desaturated,
  because a glowing red and a glowing orange are not.
- **Body text still needs 4.5:1.** Neon on dark frequently fails this. Test the
  actual values rather than assuming dark mode is automatically high contrast.

## Glow

```css
box-shadow: 0 0 0 1px rgba(var(--accent-rgb), 0.35),
            0 0 24px -4px rgba(var(--accent-rgb), 0.45);
```

- Glow the border, not the fill. A glowing fill kills the text on top of it.
- Never glow body text. `text-shadow` on paragraphs destroys legibility.
- Never animate `box-shadow` blur; animate `opacity` on a pseudo-element instead.

## Type

- **Interface and data:** monospace or a technical grotesque. Tabular figures are
  essential the moment numbers update, or the layout jitters.
- **Display:** a wide or extended grotesque works; avoid decorative "sci-fi" faces,
  which date immediately.
- Uppercase with wide tracking for labels only, never for body copy.

## Data

Futuristic interfaces are usually data interfaces, so the data has to be real.

- Real-looking values, irregular intervals, plausible units.
- Charts drawn with SVG or canvas, not decorative bars implying data that is not
  there.
- Monospaced tabular figures so columns align and updating values do not reflow.

## Motion

- Purposeful: a value updating, a state transition, a scan completing.
- Ambient motion at most one element, slow (`>8s`), low opacity, `pointer-events: none`.
- `transform` and `opacity` only. Grid animations and blur animations are what
  make these interfaces feel slow.

## Failure modes

- Glow on everything, so nothing is emphasised.
- Body text below 4.5:1 because "it's dark mode".
- Decorative charts with invented data.
- Scanline and CRT overlays on content that must be read.
- Three accent colours competing.
- Non-tabular figures in a live-updating readout, so the layout twitches.
