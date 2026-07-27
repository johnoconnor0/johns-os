# Flat Design

Two-dimensional elements. No realistic textures, gradients, bevels or heavy
shadows. Colour, shape and typography carry everything.

## The central problem

Removing shadows and gradients also removes the cues that made things look
clickable. Original flat design shipped interfaces where nobody could find the
buttons. "Flat 2.0" exists because of it.

So the rule is: **strip decoration, keep affordance.** Every interactive element
must be identifiable as interactive without a shadow. That means one of:

- a solid fill in the accent colour,
- a visible border,
- an underline (links),
- an unmistakable position and label.

Test it by asking someone to point at the buttons in a screenshot.

## Colour

Colour is doing the work that texture used to do, so it must be systematic.

- A bold, saturated palette. Flat design tolerates more saturation than most
  styles because there is nothing else carrying the visual energy.
- One accent for actions. Distinct hues for semantic states (success, warning,
  error) that are not variations of the accent.
- Blocks of colour define regions; there are no borders between sections.
- Contrast is the only depth cue available. Adjacent blocks need clearly
  different lightness, not just different hue.

## Shape

- Flat fills, no gradients. A single subtle gradient is Flat 2.0, not flat.
- Consistent radius, or none. Both are valid; mixing is not.
- Geometric icons at a uniform stroke weight, drawn on the same grid.

## Type

- Clean geometric or neo-grotesque sans. No text shadows, no letterpress.
- Weight is the main hierarchy tool since size alone reads as flat too.

## Motion

Simple and direct: colour transitions, opacity, straight-line movement. No easing
that implies mass or bounce, because nothing here has physical depth.

## Failure modes

- **Ghost buttons as primary actions.** Border-only buttons on a coloured
  background are the classic flat failure. Fill the primary action.
- **Disabled states shown only by lower opacity**, which reads as "not loaded".
  Change the cursor and remove the affordance too.
- **Colour as the only signal.** Around 8% of men have a colour vision deficiency;
  pair colour with an icon or a label for every state.
- **Enormous flat colour fields with nothing in them**, which read as unfinished
  rather than confident.
