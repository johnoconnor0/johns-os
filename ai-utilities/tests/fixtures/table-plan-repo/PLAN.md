# Store Billing

Shaped after the real plan that exposed the extractor gap: the build order lives in
markdown tables, and an unrelated six-step ordered list sits further down.

## Part 3 - Build order

### Batch 1 - blockers

| # | Task | Issue | Estimate |
| --- | --- | --- | --- |
| 1 | Add the `billing_accounts` table | WEB-101 | 2d |
| 2 | Wire `create_subscription` to the gateway | WEB-102 | 3d |
| 3 | Backfill existing customers | WEB-103 | 1d |

### Batch 2 - follow-ups

| # | Task | Issue | Estimate |
| --- | --- | --- | --- |
| 4 | Add the dunning job | WEB-104 | 2d |
| 5 | Expose `/billing/portal` | WEB-105 | 1d |

## Part 9 - Staging procedure

The Phase 3 staging checklist. This is not the plan, and before the table extractor
existed it was the only thing any extractor could see, so it became the entire
inventory.

1. Freeze the release branch
2. Snapshot the database
3. Deploy to staging
4. Run the smoke suite

## Appendix - a worked example

A numbered list inside a fence is documentation, not work:

```text
1. first the request arrives
2. then the handler runs
3. finally the response is written
```
