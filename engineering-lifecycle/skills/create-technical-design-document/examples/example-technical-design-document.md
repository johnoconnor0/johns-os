---
initiative_id: example-checkout
skill: create-technical-design-document
created_at: 2026-01-01T00:00:00+00:00
status: draft
confidence: medium
source_artifacts:
  - README.md
---

# Technical Design: Saved-Cart Checkout

## Context And Scope

Customers can save a cart but cannot pay for one. This design covers taking a
saved cart through payment to a confirmed order, for the storefront only.

The central constraint is that card data must never touch our infrastructure,
which rules out any design where the browser or our servers handle a PAN.

## Non-Goals

- Subscriptions, instalments, or any recurring charge.
- Refunds and chargebacks. Those stay in the existing admin tool.
- Multi-currency. Everything is AUD in this release.
- Replacing the existing cart storage.

## Constraints

- PCI scope must stay at SAQ-A, so payment fields are hosted by the provider.
- The provider's sandbox is the only pre-production environment available.
- Existing catalogue and cart services cannot be modified in this release.
- Peak load is 40 checkouts per minute, from the last twelve months of orders.

## Recommended Architecture

A server-side checkout-session boundary owns all interaction with the payment
provider. The Cart UI never talks to the provider directly: it calls our Checkout
API, which uses a provider adapter to create a session and returns a hosted-page
redirect URL. Payment confirmation arrives only through a verified provider
webhook, and order creation is driven by that webhook.

This keeps catalogue reads decoupled from payment writes and keeps card data
entirely inside the provider's hosted page.

## Detailed Design

**Checkout API** (`services/checkout`)
Responsibility: create and read checkout sessions. Validates the cart, re-prices
line items, calls the adapter, persists the session, returns a redirect URL.
On provider failure it returns 503 and leaves no session row.

**Provider adapter** (`services/checkout/providers/`)
A three-method interface: `createSession`, `verifyWebhook`, `parseEvent`. Thin on
purpose, so the concrete provider can change without touching callers. The
current implementation is the hosted-page provider; a second can be added behind
the same interface.

**Webhook handler** (`services/checkout/webhook`)
Verifies the signature before parsing. Idempotent on the provider event id: a
replayed event is acknowledged with 200 and does no work. Creates the order and
marks the cart converted in one transaction.

**Failure behaviour:** if the webhook never arrives, the session remains pending
and expires after 30 minutes. A reconciliation job compares pending sessions
against the provider's API once an hour and closes the gap.

## Data Design

See `data/schema.sql` in this initiative for the authoritative DDL, and
`data/entity-model.md` for ownership, sensitivity and retention.

Three changes: a new `checkout_session` table, a new `order` table, and two
nullable columns on the existing `cart` (`converted_at`, `order_id`). Unique
constraints on the provider session id and provider event id are what make
webhook processing idempotent, so they must exist before the handler is enabled.

No card data is stored. The provider's session id and the last four digits are
the only payment-related values persisted.

## API And Integration Design

| Endpoint | Purpose | Auth | Notes |
| --- | --- | --- | --- |
| `POST /checkout/sessions` | Create a session from a cart | Customer session | Idempotency key required |
| `GET /checkout/sessions/:id` | Read session state | Customer session, own session only | |
| `POST /checkout/webhook` | Provider callback | Signature verification | No customer auth |

Errors use the existing problem-detail shape. `409` for a cart already converted,
`410` for an expired cart, `503` when the provider is unreachable.

**When the provider is unavailable:** session creation fails closed with a
user-facing message. Checkout is disabled by feature flag rather than degraded,
because a partial checkout path is worse than none.

## Interfaces And Boundaries

The provider adapter is the only code permitted to import the provider SDK. A
lint rule enforces this: the boundary is worth nothing if any module can reach
past it.

The storefront depends on the Checkout API only. It has no knowledge of which
provider is in use.

## Cross-Cutting Concerns

- **Auth:** customer sessions for the two customer endpoints. The webhook
  endpoint is unauthenticated and relies entirely on signature verification, so
  that verification must run before any parsing.
- **Authorisation:** a customer may only read their own session. Enforced at the
  query, not in the handler.
- **Logging:** every session transition logs session id, cart id and provider
  event id. Never log the signature header or the raw provider payload.
- **Observability:** a counter per transition, a histogram for provider latency,
  and an alert on pending sessions older than one hour.
- **Errors:** provider errors are mapped to our own codes at the adapter boundary
  so provider vocabulary does not leak into the API.
- **Configuration:** provider keys come from the secret manager, never from env
  files committed to the repo.

## Environments

| | Preview | Development | Production |
| --- | --- | --- | --- |
| Runs on | Per-PR deploy | Local process | Managed platform |
| Database | Ephemeral, seeded | Local Postgres via Compose | Managed Postgres, pooled |
| Provider | Sandbox | Sandbox | Live |
| Webhooks | Provider sandbox to preview URL | Tunnel to localhost | Direct |
| Data | Seed script, synthetic carts | Seed script | Real |
| Config | Platform env | `.env` from `.env.example` | Secret manager |
| Deploy | Automatic on push | n/a | Tag promotion |
| Health | `/healthz` | n/a | `/healthz` plus alerting |

**Docker:** a Compose file is justified here because development needs Postgres
and a webhook tunnel. It covers those two services only; the application runs on
the host.

**New environment variables**, each added to `.env.example` as a name with a
dummy value only: `PAYMENT_PROVIDER_API_KEY`, `PAYMENT_PROVIDER_WEBHOOK_SECRET`,
`CHECKOUT_SESSION_TTL_MINUTES`, `CHECKOUT_ENABLED`.

**Production has, and development does not:** TLS termination, connection
pooling, and provider rate limits. The pooling difference matters: the
reconciliation job must not exhaust the pool, so it uses a separate limited pool.

## Alternatives Considered

- **Client-side provider SDK**, where the browser creates the session directly.
  Rejected: it pushes key handling to the client, spreads provider logic across
  the frontend, and makes server-side cart validation harder.
- **Trusting the redirect callback** to mark the order paid. Rejected: the return
  is unreliable (users close tabs) and spoofable. The webhook is the source of
  truth.
- **Polling the provider** for payment status on a timer. Rejected as higher cost
  and higher latency than a verified webhook, and it still needs idempotency, so
  it adds work without removing any.

## Risks

- Webhook retries and out-of-order delivery can create duplicate orders.
  Mitigated by idempotency on the provider event id plus a unique constraint on
  cart-to-order conversion.
- Provider outage blocks checkout entirely. Mitigated by a feature flag and a
  clear user-facing error, with an adapter interface that allows a second
  provider later.
- Price drift between cart creation and payment. Mitigated by re-validating line
  item prices at session creation and rejecting expired carts.

## Migration And Rollback

Additive only: two new tables and two nullable columns. No backfill.

Rollback is disabling `CHECKOUT_ENABLED`, which removes the entry point and lets
in-flight sessions expire naturally. The tables stay; dropping them would lose
order records. Verified in preview before release.

## ADR Candidates

- ADR: webhook as the sole source of payment truth.
- ADR: provider adapter boundary and the lint rule that enforces it.

## Open Questions

- How long does the provider keep a session valid after the customer abandons the
  hosted page? The 30 minute TTL assumes 30; unconfirmed.
- Who owns the reconciliation job's alerting rotation?
- Is CSV acceptable to auditors for the eventual order export, or is a signed
  format required?
