---
initiative_id: checkout-recovery
skill: create-ux-flow
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - 02-prd.md
---

# UX Flow

## Users

- Customer recovering checkout from the cart screen.
- Support operator reading checkout status.

## Journeys

1. Customer opens cart with no active checkout and starts checkout.
2. Customer returns to cart after a timeout and sees a pending checkout message.
3. Customer resumes valid checkout or starts a replacement after expiry.
4. Support opens order assistance view and reviews checkout status metadata.

## Screens

- Cart screen: checkout state banner, retry/resume action, cancellation notice.
- Checkout return screen: success, cancellation, and failure handling.
- Support cart detail: state timeline and latest provider metadata.

## States

- Empty cart: checkout disabled with explanation.
- Pending checkout: resume action and timestamp.
- Expired checkout: replacement action and explanation.
- Provider failure: retry action and support reference code.
- Completed checkout: confirmation link.

## Edge Cases

- Cart content changed after provider session creation.
- Customer opens the cart in two browser tabs.
- Webhook updates state while the customer is reading the cart screen.

## Accessibility

Checkout state banners must be announced to screen readers and must not rely on color alone.

## Open Questions

- [ ] Confirm exact customer-facing copy for provider failures.
