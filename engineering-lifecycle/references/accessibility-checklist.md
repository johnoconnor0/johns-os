# Accessibility Checklist

Use this checklist when creating design-system accessibility rules. Do not claim compliance unless a qualified accessibility review and relevant checks have been completed.

## Keyboard

- Interactive elements are keyboard reachable.
- Focus order follows visual and logical order.
- Custom controls preserve expected keyboard semantics.
- Escape and tab behaviour are defined for dialogs, menus, popovers, and drawers.

## Focus

- Focus state is visible.
- Focus is not trapped except in modal/dialog patterns.
- Modal focus returns to the triggering control when closed.
- Skip links or landmark structure are considered for larger apps.

## Text And Labels

- Form fields have visible labels or accessible names.
- Buttons and links describe their action.
- Icon-only controls have accessible labels.
- Headings describe page and section structure.

## Colour And Contrast

- Colour is not the only signal for status, selection, or errors.
- Error and success states include text or icon support.
- Proposed colour combinations require contrast checking before production use.

## Errors And Feedback

- Error messages identify the issue and recovery action.
- Form errors are associated with fields where possible.
- Loading and success feedback are understandable to screen reader users where relevant.

## Motion

- Avoid unnecessary motion.
- Respect reduced-motion preferences where possible.
- Do not rely on animation alone to communicate state.

## Component-Specific Notes

| Component | Accessibility Requirement |
| --- | --- |
| Button | Native button semantics, visible focus, disabled/loading semantics |
| Modal | Labelled title, focus management, escape close, return focus |
| FormField | Label, hint text, error association |
| Table | Header cells and readable responsive strategy |
| Tabs | Keyboard navigation and selected state semantics |
