# Design Rules

> Enforceable rules — every entry is falsifiable by automated check or focused review.
> For non-testable beliefs, see [principles.md](./principles.md).

### Color

- Brand color MUST be `--brand` (resolves to `hsl(240 5.9% 10%)`). Never inline a hex value.
- Semantic colors (`--success`, `--danger`, `--warning`, `--info`) MUST come from [foundations/color.md](../components/foundations/color.md). No new semantic colors without DS update.
- Surface colors MUST use `--bg-*` tokens, never `#fff` or `#000` directly.
- Error states MUST set BOTH `border-color: --danger` AND show error text. Border-only error indication is forbidden (see principle 1).

### Spacing

- Use `--space-1` through `--space-16` only. No arbitrary px values in CSS or inline styles.
- `--space-3` (12px) is the standard control padding; `--space-4` (16px) is the standard card padding.
- Margins SHOULD follow the same scale; ad-hoc `margin: 13px` is forbidden.

### Typography

- Text uses `--font-body` (Inter). Headings use `--font-heading` (Inter or per DS).
- Font sizes MUST be from the type scale tokens (`--text-xs` through `--text-5xl`).
- Line-height MUST be a token (`--leading-tight`, `--leading-normal`, `--leading-relaxed`).
- NEVER set font weight as a bare number; use semantic weights (`--font-regular`, `--font-medium`, `--font-semibold`, `--font-bold`).

### Radius

- Control radius MUST be `--radius-md` (8px).
- Card radius MUST be `--radius-lg` (12px).
- Pill / fully-rounded MUST be `--radius-full`.
- NEVER mix radius values within one component.

### Shadow

- Elevation MUST come from `--shadow-sm`, `--shadow-md`, `--shadow-lg`.
- Inline `box-shadow: 0 1px 3px ...` is forbidden.

### Interactive states

- Every interactive element MUST have a visible focus state. `outline: none` without a custom focus indicator is forbidden.
- Disabled states MUST set BOTH `opacity` AND `cursor: not-allowed`, AND remove pointer events.
- Hover states MUST NOT be the only signal of interactivity (touch / keyboard users get nothing). Pair with a visible affordance (cursor, underline, icon).

### Component selection

- A `<Button>` is for actions. A `<Link>` is for navigation. Never style one as the other.
- Form inputs MUST use the canonical `<Input>` component. Custom inputs go in `local-components/` with a justification comment.
- Modals MUST use the canonical `<Modal>` (when defined). Ad-hoc fixed-position overlays are forbidden.

### Tokens consumed (drift contract)

- Every component spec in [components/](../components/components/) MUST list `## Tokens consumed`.
- `/check-drift` enforces that every token referenced exists in [foundations/](../components/foundations/).
- A missing token reference in foundations is a hard drift failure, not a warning.
