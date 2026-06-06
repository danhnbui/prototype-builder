# Button

> A button performs an action. For navigation, use `<Link>`. For form submission, use `<Button type="submit">`.

## Anatomy

- container · (optional) leading-icon · label · (optional) trailing-icon

## Properties

| Prop | Values | Default |
|---|---|---|
| `variant` | `primary` / `secondary` / `ghost` / `danger` / `link` | `primary` |
| `size` | `sm` / `md` / `lg` | `md` |
| `iconOnly` | `true` / `false` | `false` |
| `disabled` | `true` / `false` | `false` |
| `loading` | `true` / `false` | `false` |
| `fullWidth` | `true` / `false` | `false` |

## Sizes

| Size | Height | Padding | Text |
|---|---|---|---|
| `sm` | 32px | `--space-3` `--space-4` | `--text-sm` semibold |
| `md` | 40px | `--space-4` `--space-5` | `--text-base` semibold |
| `lg` | 48px | `--space-5` `--space-6` | `--text-md` semibold |

Icon-only sizes are square: 32 / 40 / 48px.

## States

| State | Visual |
|---|---|
| default | base fill + border |
| hover | hover fill (slight tint adjustment) |
| active (pressed) | active fill (deeper tint) |
| focus | base + 2px focus ring (`outline: 2px solid var(--brand); outline-offset: 2px`) |
| disabled | `opacity: 0.5`, `cursor: not-allowed`, pointer-events suppressed |
| loading | label replaced with spinner; disabled-equivalent until resolved |

## Tokens consumed

### All variants
- Sizing: `--space-3` … `--space-6`
- Corner: `--radius-md`
- Typography: `--font-body`, `--font-semibold`, `--text-sm` / `--text-base` / `--text-md`
- Transition: `background 0.12s, border-color 0.12s, color 0.12s`

### Per variant

| Variant | Background | Border | Text | Hover bg |
|---|---|---|---|---|
| `primary` | `--brand` | none | `--brand-foreground` | `--brand` @ 90% lum |
| `secondary` | `--bg` | `--border-strong` | `--text-primary` | `--bg-soft` |
| `ghost` | transparent | none | `--text-primary` | `--bg-soft` |
| `danger` | `--danger` | none | `--brand-foreground` | `--danger` @ 90% lum |
| `link` | transparent | none | `--brand` | underline appears |

## Usage

- **USE** for the primary call-to-action on a screen
- **USE** `secondary` or `ghost` for less-emphasized actions next to a primary
- **USE** `link` for inline actions that read as text (e.g., "Forgot password?")
- **AVOID** `primary` for navigation — that's a link
- **AVOID** two `primary` buttons on the same screen (see principle 4)
- **AVOID** `danger` for routine destructive actions — pair with confirmation

## Do / Don't

✅ One primary action per screen
✅ `disabled` state explains why disabled (tooltip or helper text)
✅ Icon-only button has `aria-label`

❌ Hover-only state changes (touch + keyboard users get nothing)
❌ Mixing button and link styles in one row
❌ Disabled without explanation

## Code reference

- HIVE component: `<Button>` (PG only)
- Shadcn equivalent: `<Button>`
- Storybook: TBD
