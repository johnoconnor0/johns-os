# Neumorphism (soft UI)

Elements appear extruded from or pressed into the background, formed by a paired
light and dark shadow from a single consistent light source.

## The accessibility warning, first

Neumorphism fails WCAG contrast **by construction**. The entire effect depends on
the element and its background being nearly the same colour. That is not a bug to
work around; it is what the style is.

Therefore:

- **Never use it for primary text, form labels, error states, or anything an
  assistive user must find.** Text sits *on* neumorphic surfaces at full contrast,
  it is never *made of* them.
- **Every interactive element needs a non-shadow affordance.** If pressed and
  unpressed differ only by shadow direction, users with low vision, on a dim
  screen, or in sunlight cannot tell. Add colour, a border, or a label change.
- **Focus rings must be a solid high-contrast outline**, never a shadow variation.

Given that, reserve this style for decorative surfaces, dashboards with large
touch controls, and audio or hardware-style interfaces. Do not use it for forms,
dense data, or anything safety-critical.

## Recipe

```css
background: var(--bg);                 /* identical to the page background */
box-shadow:
  6px 6px 12px var(--shadow-dark),     /* away from the light */
 -6px -6px 12px var(--shadow-light);   /* toward the light */
```

Pressed (inset):

```css
box-shadow:
  inset 5px 5px 10px var(--shadow-dark),
  inset -5px -5px 10px var(--shadow-light);
```

- **A mid-tone background is mandatory.** The effect needs room for a shadow both
  lighter and darker than the surface, so it cannot work on white or black.
  `#E0E5EC` is the canonical light value.
- **One light source for the whole page.** Top-left is conventional. Mixed shadow
  directions read as broken rendering.
- Shadow colours are derived from the background, not black and white: roughly
  ±12% lightness.
- Radius is generous (`12px` to `24px`); sharp corners break the extrusion.

## Colour

Monochrome by nature. One accent used at full saturation for the elements that
must be found: primary actions, active states, alerts. The accent is the only
thing on the page that is not the background colour.

## Motion

Short and physical. `150ms` `ease-out` between raised and inset. The state change
is the animation; nothing else needs to move.

## Failure modes

- Text rendered in the shadow effect instead of on top of it.
- Toggle or checkbox states distinguished only by shadow direction.
- Applied on white, where the light shadow is invisible.
- Two light sources, or shadows that switch direction between components.
- Used for a dense form, where every field becomes a low-contrast trough.
