# Material Design

Google's system: structured grids, layered surfaces, elevation, motion, and a
familiar component vocabulary.

## Use the real package

For production, install `@material/web` and Material 3 tokens. Recreating Material
by hand produces something that looks like Material and behaves wrong: the ripple
timing, the state layers, the focus order and the motion curves are the system.

`starter.html` here is a **token-accurate approximation** for prototypes only. It
exists so a prototype can be produced without a build step. Say so when you use it.

## Tokens

Material 3 is token-driven. The set that matters:

- `primary` / `on-primary`, `secondary`, `tertiary`, `error`
- `surface`, `surface-container` (five levels), `on-surface`, `on-surface-variant`
- `outline`, `outline-variant`

Generate the palette from one seed colour rather than picking values. Every role
derives from the seed with defined tone steps (0-100), which is what keeps
contrast correct in both light and dark.

## Elevation

Elevation is a hierarchy, not decoration. Levels mean "closer to the user".

| Level | Used for |
| --- | --- |
| 0 | Page background |
| 1 | Cards at rest |
| 2 | Raised buttons, top app bar on scroll |
| 3 | Menus, FAB |
| 4-5 | Dialogs, navigation drawer |

In Material 3 elevation is expressed mainly by **surface tint** (a tone of the
primary colour mixed into the surface), with shadow as a secondary cue. Random
elevations flatten the meaning of all of them.

## Shape

A shape scale, not ad-hoc radii: none `0`, extra-small `4px`, small `8px`,
medium `12px`, large `16px`, extra-large `28px`, full `999px`. Each component
class has an assigned step.

## Motion

- Standard easing `cubic-bezier(0.2, 0, 0, 1)`, `200ms` to `300ms`.
- Emphasised easing for large transitions, `400ms` to `500ms`.
- State layers: hover `8%`, focus `10%`, pressed `10%` of `on-surface` over the
  component.

## Failure modes

- **Shipping default purple.** Material 3's baseline scheme is the Material
  equivalent of AI purple. Theme from a real seed colour.
- **Mixing systems.** No shadcn or Carbon components inside a Material tree.
- **Elevation as decoration**, so nothing reads as closer than anything else.
- **Hand-rolled ripple.** Either use the real component or use a plain state
  layer; a half-implemented ripple feels broken.
- **Touch targets under 48px.** Material specifies 48, not 44.
