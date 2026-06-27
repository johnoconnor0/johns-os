# Prototype Scope Guide

Use this guide to keep UI prototype work intentionally small, useful, and honest about what is mocked.

## Mode Selection

| Mode | Use When | Avoid When |
| --- | --- | --- |
| Static UI mock | Visual hierarchy, screen composition, or state exploration is the goal | Navigation and interactions are the main thing to validate |
| Clickable prototype | Demoable flow, transitions, forms, or local interactions matter | The user expects production persistence or real integrations |
| Vertical MVP slice | A thin real journey can use approved APIs or data contracts | Backend contracts, auth, or permissions are still unresolved |
| Dashboard/app shell | Navigation and information architecture are the core value | The user needs deep workflow logic or backend implementation |

## Scope Rules

- Build the smallest useful prototype that demonstrates the core product value.
- Prefer one complete journey over many incomplete screens.
- Include enough state coverage to make the demo credible.
- Exclude screens that do not change the product learning goal.
- Keep mock data visibly separated from production data paths.
- Do not add dependencies unless they already match repo conventions or are necessary for the prototype.

## Data Strategy

Prefer this order:

1. Existing local mock or fixture conventions.
2. New local mock data in a clearly named prototype or fixture location.
3. Existing approved API or data contracts for a vertical slice.
4. Inline data only for very small isolated prototypes.

Do not present a mock integration as a real provider connection.

## Scope Statement Checklist

- Prototype mode is explicit.
- User journey is one sentence.
- Included screens are named.
- Excluded screens have reasons.
- Mocked behaviour is distinct from real behaviour.
- Known limitations include productionisation needs.
- Validation commands are selected from actual project scripts.
