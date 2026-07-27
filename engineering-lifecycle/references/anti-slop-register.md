# Anti-Slop Register

Patterns that make generated interfaces read as machine-made. Each entry names the
pattern, why it reads that way, **when it is legitimate**, and what to do instead.

This is not a ban list. Almost every pattern here is the right answer for some
brief. The failure is reaching for it *by default*, which is what produces the
sameness. Before rejecting a pattern, check its override condition — if the brief
genuinely calls for it, use it deliberately and say so.

## Provenance

Sections 1 to 6 are adapted from [taste-skill](https://github.com/Leonxlnx/taste-skill)
by Leonxlnx, MIT licensed, © 2026. Sections 7 to 10 are this project's own,
covering aesthetics and modes that upstream does not.

`scripts/anti-slop-check.py` mechanically detects the subset of these that can be
found by inspection. Everything else needs judgement.

---

## 1. The Default Reach

The single strongest signal. Before generating, state the design read in one line:
*"Reading this as: `<page kind>` for `<audience>`, with a `<vibe>` language."*

| Pattern | Why it reads as AI | Legitimate when | Instead |
| --- | --- | --- | --- |
| Purple/violet gradient hero over dark mesh | The most-generated aesthetic of the era. Recognisable at a glance. | The brand's actual colour is purple. | Neutral base (zinc/slate/stone) with one high-contrast accent. |
| Three equal feature cards in a row | Nothing about the content required three, or equality. | The three items genuinely are peers of equal weight. | 2-column zig-zag, asymmetric grid, scroll-pinned sequence, horizontal scroll. |
| Inter + slate-900 | The default of the default. | Explicitly asked for a neutral/Linear feel, or accessibility-first public sector. | Geist, Outfit, Cabinet Grotesk, Satoshi, or a brand-appropriate face. |
| Glassmorphism applied to everything | A material used as decoration rather than for depth. | Layering genuinely needs to communicate depth over a busy background. | Use it on one layer that needs to float. Solid fallback for `prefers-reduced-transparency`. |
| Infinite-loop micro-animations everywhere | Motion with no communicative purpose. | The motion conveys state or draws the eye once. | Motion on entry and interaction only. Respect `prefers-reduced-motion`. |

## 2. Typography

| Pattern | Why | Legitimate when | Instead |
| --- | --- | --- | --- |
| Serif display because the brief said "creative" | "Creative equals serif" is a learned reflex, not a design decision. | The aesthetic is genuinely editorial, luxury, publication, heritage, and you can say why *this* serif fits *this* brand. | Sans display: Geist Display, PP Neue Montreal, GT Walsheim, Cabinet Grotesk Display. |
| `Fraunces` / `Instrument Serif` as the display face | The two most-reached-for display serifs in generated work. | Named by the brand. | Rotate: PP Editorial New, GT Sectra, Reckless Neue, Tiempos Headline, Recoleta, Canela. |
| A random serif word inside a sans headline | Mixed-family emphasis reads as amateur. | Never, as an emphasis device. | Italic or bold of the *same* family. |
| Oversized H1 doing all the hierarchy work | Scale substituting for structure. | A genuine statement hero with little else on screen. | Control hierarchy with weight, colour and spacing; scale last. |
| Gradient text on large headings | Decoration applied to type instead of designing the type. | The gradient is the brand. | Solid colour. If emphasis is needed, change weight or size. |
| `leading-none` on italic display type with descenders | Clips `y g j p q`. A rendering bug, not a style. | Never. | `leading-[1.1]` minimum plus `pb-1` reserve. |

## 3. Colour

| Pattern | Why | Legitimate when | Instead |
| --- | --- | --- | --- |
| Pure black `#000000` | Nothing physical is pure black; it reads as unset rather than chosen. | Deliberate OLED or high-contrast mode. | `zinc-950`, `#0A0A0A`, charcoal. |
| Neon outer glows | Glow as a substitute for hierarchy. | Genuinely futuristic/cyberpunk brief. | Inner borders, subtle tinted shadows. |
| More than one accent colour | Reads as no palette rather than a rich one. | A deliberate multi-brand or category-coded system. | One accent, locked, audited across every section. |
| Accent drift between sections | A warm-grey site with a blue CTA in section 7. | Never. | Pick the accent once; audit every component before shipping. |
| Beige/cream + brass + espresso for premium consumer | The default "artisan" palette. Makes every brand look like the same brand. | The brand's actual palette. | Cold luxury (silver/chrome/smoke), forest (deep green/bone/amber), or the brand's real colours. |
| Oversaturated accents | Fights the neutrals instead of sitting in them. | Deliberately loud consumer brief. | Desaturate below ~80%. |

## 4. Layout

| Pattern | Why | Legitimate when | Instead |
| --- | --- | --- | --- |
| `h-screen` full-height hero | Jumps on mobile when the browser chrome collapses. | Never. | `min-h-[100dvh]`. |
| Flexbox percentage math (`w-[calc(33%-1rem)]`) | Fragile arithmetic where a grid expresses the intent. | Never for grids. | `grid grid-cols-1 md:grid-cols-3 gap-6`. |
| Hairline `border-t` **and** `border-b` on every row | The laziest possible list treatment. | Never both. | One border direction, sparingly, or no borders with spacing instead. |
| Crosshairs and grid lines as decoration | Lines drawn to look designed rather than to organise. | The lines mark a real structural grid the content uses. | Remove them, or make them carry the layout. |
| A small explainer floating in a section header's top-right | Aligned to nothing; the giveaway of a generated header. | Never. | Put it under the headline, or build a proper two-column header. |
| Vertical rotated text | Agency-portfolio cliché. | Explicitly experimental/Awwwards brief where it serves the composition. | Horizontal. |

## 5. Content Realism

Fake content is the fastest tell, because real products have messy data.

| Pattern | Why | Legitimate when | Instead |
| --- | --- | --- | --- |
| "John Doe", "Jane Smith", "Sarah Chan" | Placeholder names shipped as content. | Never. | Realistic, locale-appropriate names. |
| "Acme", "Nexus", "SmartFlow", "Cloudly" | Generated-sounding brand names. | Never. | Names that sound like real companies in that market. |
| Round numbers: `99.99%`, `50%`, `1,234,567` | Real metrics are not round. | A genuine round figure (a price, a limit). | Organic values: `47.2%`, `+61 3 9412 8871`. |
| `Lorem ipsum` | Unfinished work presented as finished. | Never in a deliverable. | Write plausible copy for the actual product. |
| "Elevate", "Seamless", "Unleash", "Next-Gen", "Revolutionize" | Filler verbs that say nothing. | Never. | Concrete verbs describing what it does. |
| Generic avatars (SVG "egg", user icon) | Placeholder shipped as content. | A genuine no-avatar state. | `https://picsum.photos/seed/<name>/200/200` or real assets. |

## 6. Production Tells

Small decorations that cluster in generated work.

| Pattern | Why | Legitimate when |
| --- | --- | --- |
| Version labels in the hero (`v2.0`, `BETA`, `EARLY ACCESS`) | Status theatre. | The brief is genuinely about launch status. |
| Section-number eyebrows (`001 · Capabilities`, `06 · How it works`) | Enumeration for its own sake. | A genuine sequence the reader must follow in order. |
| Middle dot `·` as the universal separator | One line of `foo · bar · baz · qux`. | Max one per metadata line. |
| Scroll cues (`↓ Scroll`, animated mouse icon) | The reader knows what scrolling is. | A genuinely non-obvious interaction. |
| Locale/time/weather strips (`LIS 14:23 · 18°C`) | Atmosphere with no function. | Distributed studio where timezone matters, travel brand, physical venue. |
| Decorative coloured status dots | A dot before every nav item and badge. | The dot conveys real state (server status, availability), used once per section. |
| Version footers on marketing pages (`v1.4.2`, `Build 0048`) | Devtool fixture on a landing page. | Docs sites and changelogs. |
| `div`-based fake product screenshots | The single strongest tell. Fake UI built from styled rectangles. | Never. Use a real screenshot, a generated image, a real component, or nothing. |
| Poetic section labels ("From the field", "On our desks") | Performative craftsmanship. | Never as a default. |
| Hand-rolled SVG icons | Inconsistent weights and grids against a real icon set. | A genuine logo or bespoke illustration. |
| Em-dash `—` in visible copy | The strongest textual tell in generated interfaces. | Rare. Prefer a period, comma, colon, or parentheses. Ranges use a hyphen. |

## 7. Glassmorphism (our research)

Translucent panels over a blurred backdrop.

- **Needs something behind it.** Glass over a flat colour is just a grey box. If
  there is no image, gradient or content behind, the material is wrong.
- **Contrast survives the blur or the text is unreadable.** Check the worst-case
  backdrop, not the demo one. Add a semi-opaque scrim under text.
- **`prefers-reduced-transparency` must get a solid fallback.** Not optional.
- **`backdrop-filter` is expensive.** A handful of layers, not a page of them.
- **One glass layer deep.** Glass on glass reads as a rendering error.

## 8. Neumorphism (our research)

Soft extruded shapes made from paired light and dark shadows.

- **Fails WCAG contrast by construction.** The whole effect is low contrast. Never
  use it for primary text, form labels, error states, or anything an assistive
  user must find. Reserve it for decorative surfaces.
- **Interactive elements need a non-shadow affordance.** If pressed and unpressed
  differ only by shadow direction, most users cannot tell. Add colour or a border.
- **Requires a mid-tone background.** It cannot work on white or black; the effect
  needs room for both a lighter and a darker shadow.
- **One light source for the whole page.** Mixed shadow directions read as broken.

## 9. Material Design (our research)

- **Use the real package.** `@material/web` plus Material 3 tokens. Recreating
  Material by hand produces something that looks like Material and behaves wrong.
- **Elevation is a hierarchy, not decoration.** Levels mean "closer to the user".
  Random elevations flatten the meaning.
- **Theme it or it looks like an unstyled demo.** Default Material 3 purple is the
  Material equivalent of AI purple.
- **Do not mix with another system.** No shadcn components inside a Material tree.

## 10. Modes And Aesthetics

| Aesthetic | Default failure | Correction |
| --- | --- | --- |
| **Flat design** | Removing shadows also removes affordance; nothing looks clickable. | Keep affordance in colour, weight, spacing and state changes. Test that a button reads as a button. |
| **Editorial** | Magazine layout applied to non-magazine content, so nothing is readable. | Requires real long-form content and real imagery. Measure stays 60-75 characters. |
| **Brutalist** | "Unstyled" used as an excuse for unconsidered. | Brutalism is rigorously gridded and typographically precise. Every raw edge is deliberate. |
| **Futuristic** | Neon on black with glow on everything; unreadable and slow. | One accent, restrained glow, real data. Dark mode still needs 4.5:1 body text. |
| **Minimalist** | Empty rather than reduced; the work is not done, it is absent. | Reduction means every remaining element is load-bearing. Whitespace is a composition tool, not a gap. |

## Pre-Flight Check

Before presenting any generated interface:

1. Zero em-dashes in visible copy.
2. Zero placeholder names, brands or `Lorem ipsum`.
3. One accent colour, consistent across every section.
4. No `#000000`; no `h-screen` hero.
5. No `div`-built fake screenshots.
6. Renders in both light and dark.
7. `prefers-reduced-motion` and `prefers-reduced-transparency` honoured.
8. Body text meets 4.5:1; interactive targets at least 44px.
9. Every icon comes from one library.
10. The design read stated at the start still matches what was built.
