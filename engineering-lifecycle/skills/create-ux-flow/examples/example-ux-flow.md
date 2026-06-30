---
initiative_id: example-checkout
skill: create-ux-flow
created_at: 2026-01-01T00:00:00Z
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# UX Flow

## Users

| User / Role | Goal | Entry Point |
| --- | --- | --- |
| Shopper | Pay for items in the cart and receive confirmation | Cart screen "Checkout" button |
| Returning shopper | Reuse a saved card and check out quickly | Cart screen with a stored payment method |
| Support agent | Help a shopper whose checkout failed | Internal order lookup linked from a support ticket |

## Journeys

| Journey | Steps | Success Outcome |
| --- | --- | --- |
| Standard checkout | Review cart, select checkout, pay on hosted page, return to confirmation | Order is recorded and confirmation page shows the order number |
| Cancelled checkout | Select checkout, cancel on the hosted page, return to cart | Cart items are preserved and no charge is made |
| Recovery after failure | Checkout fails, see error, retry, complete payment | Order succeeds on retry without duplicate charges |

## Screens

| Screen | Purpose | Primary Action | Exit |
| --- | --- | --- | --- |
| Cart | Review items and totals before paying | Select "Checkout" | Hosted payment page |
| Hosted payment page | Collect payment securely via Stripe | Submit payment | Confirmation or cart |
| Confirmation | Reassure the shopper the order succeeded | View order details | Order history |
| Checkout error | Explain a recoverable failure and offer retry | Select "Try again" | Cart or hosted payment page |

## States

| State | Trigger | UI Behavior | Recovery |
| --- | --- | --- | --- |
| Loading | Session is being created | Disable the checkout button and show a spinner | Re-enable on response |
| Empty | Cart has no items | Hide checkout and show "Your cart is empty" | Link back to browsing |
| Error | Provider or network failure | Show a recoverable message with a retry action | Retry creates a fresh session |
| Permission | Session belongs to another account | Show "This checkout is no longer available" | Return to cart |
| Success | Webhook confirms payment | Render confirmation with the order number | Link to order history |

## Edge Cases

- Edge case: Shopper double-clicks "Checkout".
- Expected behavior: Only one session is created; the second click is ignored while loading.
- Edge case: Shopper returns to a session that has already expired.
- Expected behavior: Show the expired-session message and offer to start a new checkout.
- Edge case: Webhook confirming payment is delayed past the redirect.
- Expected behavior: Confirmation page shows a pending state, then resolves when the webhook lands.

## Accessibility

- Keyboard: The checkout button, retry action, and confirmation links are reachable and operable by keyboard.
- Screen reader: Loading and error states announce changes via a polite live region.
- Color/contrast: Error and success messaging meets WCAG AA contrast and does not rely on color alone.
- Motion: The loading spinner respects the reduced-motion preference.

## Open Questions

- [ ] Should the confirmation page wait for the webhook, or confirm optimistically on redirect return?
- [ ] Do returning shoppers need an in-app card picker, or is the hosted page sufficient for v1?
