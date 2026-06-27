# Component State Guide

Use this guide when defining reusable components, variants, states, behaviours, and anti-patterns.

## Starter Component Set

For MVPs and prototypes, start with:

- Button
- Input
- Textarea
- Select
- Checkbox
- Radio
- Card
- Badge
- Alert
- Modal
- Drawer
- Tabs
- Table
- EmptyState
- LoadingState
- ErrorState
- Sidebar
- TopNav
- PageHeader
- MetricCard
- FormField

## Component Spec Checklist

For each component, define:

- Purpose.
- Variants.
- States.
- Props or data inputs.
- Accessibility rules.
- Responsive behaviour.
- Usage examples.
- Anti-patterns.

## State Coverage

| State | Required When | Notes |
| --- | --- | --- |
| Default | Component is usable | Baseline state |
| Hover | Pointer interactions exist | Do not rely only on hover |
| Focus | Component is interactive | Must be visibly keyboard reachable |
| Active | Pressed or selected action matters | Keep distinct from focus |
| Disabled | Action can be unavailable | Explain reason when user action is blocked |
| Loading | Action or data fetch takes time | Prevent layout shift where possible |
| Empty | Data set can be empty | Explain next action |
| Error | Input, request, or data can fail | Include recovery path |
| Success | User action can complete | Confirm outcome |
| Selected | Choice or navigation state exists | Use more than colour when needed |
| Permission | Access can be restricted | Avoid leaking sensitive data |

## Anti-Patterns

- Creating many variants before there is a product need.
- Defining visual states without behaviour or accessibility requirements.
- Using raw colour values directly in component specs when semantic tokens are available.
- Duplicating components that already exist in the repo.
- Treating component examples as production-ready code without implementation review.
