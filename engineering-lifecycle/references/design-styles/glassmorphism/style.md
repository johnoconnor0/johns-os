# Glassmorphism

Translucent panels over a blurred backdrop, soft borders, layered depth. The
material reads as frosted glass floating above content.

## The precondition

Glass needs something behind it. Over a flat colour it is just a grey box with a
border. If there is no image, gradient, video or content beneath the panel, this
is the wrong material and the answer is a solid surface.

## Recipe

```css
background: rgba(255,255,255,0.10);   /* dark mode: 0.06-0.12 */
backdrop-filter: blur(16px) saturate(160%);
border: 1px solid rgba(255,255,255,0.18);
box-shadow: 0 8px 32px rgba(0,0,0,0.18);
```

- Blur radius `12px` to `24px`. Below that it reads as dirty rather than frosted.
- `saturate()` above 100% keeps colour alive through the blur.
- The border is what makes it read as a pane. Without it, the panel has no edge.
- A subtle top highlight (a `1px` lighter inset) suggests a lit edge.

## Depth

One glass layer deep. Glass on glass reads as a rendering error. Where two levels
are needed, make the lower one solid and the upper one glass.

## Colour

- The backdrop carries the colour; the glass is close to neutral.
- One accent, at full opacity, so it stays legible through the material.
- Avoid the mesh-gradient-plus-purple default. A photograph, a single deep
  gradient, or real content behind the glass all read as more considered.

## Accessibility

This is where glassmorphism usually fails.

- **Text on glass must clear 4.5:1 against the worst-case backdrop**, not the demo
  one. If the backdrop can be light or dark, add a semi-opaque scrim beneath the
  text.
- **`prefers-reduced-transparency` gets a solid fill.** Required, not optional.
- **Focus rings need to be visible against a blurred background.** Use a solid
  high-contrast ring, not a translucent one.

## Performance

`backdrop-filter` compositing is expensive and forces a new layer. A handful of
glass panels per view; never one per list row. Never animate the blur radius.

## Failure modes

- Glass applied to everything, so nothing floats relative to anything.
- Blur over a flat background, producing a grey box.
- Body text placed directly on glass without a scrim.
- Mesh gradient plus violet plus glass: the most-generated combination there is.
