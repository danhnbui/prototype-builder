# Input

> Single-line text input. For multi-line, use `<Textarea>`. For password, use `<Input type="password">` with the canonical visibility toggle.

## Anatomy

- container · (optional) leading-icon · text-field · (optional) trailing-icon · (optional) clear-button

External to the input itself: label (above), helper text or error message (below). Always include a label.

## Properties

| Prop | Values | Default |
|---|---|---|
| `type` | `text` / `email` / `password` / `tel` / `url` / `search` / `number` | `text` |
| `size` | `sm` / `md` / `lg` | `md` |
| `state` | `default` / `error` / `success` | `default` |
| `disabled` | `true` / `false` | `false` |
| `readOnly` | `true` / `false` | `false` |
| `required` | `true` / `false` | `false` |
| `placeholder` | string | none |
| `clearable` | `true` / `false` | `false` |

## Sizes

| Size | Height | Padding-x | Text |
|---|---|---|---|
| `sm` | 32px | `--space-3` | `--text-sm` |
| `md` | 40px | `--space-4` | `--text-base` |
| `lg` | 48px | `--space-5` | `--text-md` |

## States

| State | Visual |
|---|---|
| default | `--bg` fill + `--border-strong` border |
| hover (not focused) | border darkens slightly |
| focus | border = `--brand`, 2px focus ring matching `--brand` at ~30% opacity |
| filled | same as default (no special state for "has value") |
| error | border = `--danger`, error message in `--danger` below + `aria-invalid="true"` |
| success | border = `--success` (optional success message) |
| disabled | `opacity: 0.5`, `cursor: not-allowed`, `bg: --bg-soft` |
| readOnly | same as disabled visually, but selectable |

## Tokens consumed

- Container: `--bg` fill, `--border-strong` border, `--radius-md` corners
- Spacing: `--space-3` / `--space-4` / `--space-5` per size
- Typography: `--font-body`, `--text-sm` / `--text-base` / `--text-md`
- Focus: `--brand` outline
- Error: `--danger` border + text
- Disabled: `--bg-soft` fill
- Icons: `--icon-md` size, `--text-tertiary` color

## Usage

- **USE** for collecting short text input
- **USE** `type="password"` with visibility toggle for credentials
- **USE** `type="email"` / `tel` / `url` for typed input — enables mobile keyboard hints
- **AVOID** for long-form input — use `<Textarea>`
- **AVOID** placeholder-as-label — always include a separate `<label>` (see [accessibility.md → ARIA](../../guidelines/accessibility.md))

## Error pattern

Error states MUST display BOTH:
1. Border color = `--danger`
2. Error message text below the input, in `--danger` color, describing the problem AND the fix

```
[ Email field with red border ]
✗ Enter a valid email address (e.g., name@example.com)
```

Per principle 1 ("Errors state the outcome, never color alone"), border-only error indication is forbidden.

## Do / Don't

✅ Always pair with a visible label
✅ Error message states the problem AND the fix
✅ Error clears when user begins editing
✅ `aria-describedby` links the input to its helper / error text
✅ `aria-invalid="true"` set when in error state

❌ Placeholder as label
❌ Red border with no error message
❌ Errors that only say "Invalid" without explanation

## Code reference

- HIVE component: `<InputField>` (PG only)
- Shadcn equivalent: `<Input>`
- Storybook: TBD
