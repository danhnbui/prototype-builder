# Accessibility

> Subset of [rules.md](./rules.md) focused on a11y. Separated for visibility — these have legal and usability stakes.

### Color contrast

- Body text vs background MUST meet WCAG 2.2 AA (4.5:1 for normal text, 3:1 for large text/UI).
- Focus indicators MUST be 3:1 against their background.
- Brand color used as text MUST be on `--bg-on-brand` (the paired surface), never on a busy or photo background.

### Focus management

- Every interactive element MUST have a visible focus ring of at least 2px.
- Focus order MUST follow visual reading order (top-to-bottom, left-to-right in LTR).
- Modal/dialog open: focus MUST move to the first focusable element inside. Close: focus MUST return to the element that opened it.
- Skip-to-content link MUST be the first focusable element on every screen.

### Keyboard

- Every action MUST be reachable by keyboard (Tab + Enter/Space).
- Custom widgets MUST follow the ARIA Authoring Practices Guide for their pattern (combobox, dialog, menu, etc.).
- ESC closes overlays; ENTER submits the primary action; SPACE toggles checkboxes/buttons.

### ARIA & semantics

- Use native HTML elements first (`<button>`, `<a>`, `<label>`). Only add `role=` when no native element fits.
- Form inputs MUST have an associated `<label>` (visible or `aria-label` with justification).
- Icon-only buttons MUST have `aria-label`.
- Errors associated with form fields MUST use `aria-describedby` AND `aria-invalid="true"`.

### Motion

- Animations MUST respect `prefers-reduced-motion: reduce` — disable or shorten transitions.
- No flashing content faster than 3Hz (seizure trigger threshold).
- Auto-rotating content MUST be pauseable.

### Touch targets

- Minimum touch target size: 44×44px (iOS HIG) / 48×48dp (Material).
- Adjacent interactive elements MUST have at least 8px of separation.
