# Icon Tokens

> Lucide icon set. Stroke-based monoline icons; consistent visual weight.

## Library

| Property | Value |
|---|---|
| Set | Lucide ([lucide.dev](https://lucide.dev)) |
| Style | Outline, 24px viewBox, 2px stroke |
| License | ISC (free for commercial use) |

## Size scale

| Token | Size | Usage |
|---|---|---|
| `--icon-xs` | 12px | Inline with `--text-xs` (badges, tags) |
| `--icon-sm` | 16px | Inline with `--text-base`, dense UI |
| `--icon-md` | 20px | **Default control icon** (buttons, inputs) |
| `--icon-lg` | 24px | Card header icons, navigation |
| `--icon-xl` | 32px | Feature illustrations, empty states |
| `--icon-2xl` | 48px | Hero / decorative |

## Stroke weight

| Token | Value | Usage |
|---|---|---|
| `--icon-stroke` | 2px | Default |
| `--icon-stroke-thin` | 1.5px | Subtle / decorative |
| `--icon-stroke-bold` | 2.5px | Emphasis / brand moments |

## Hard rules

- Icon size MUST be a `--icon-*` token, never an inline px value.
- Custom icons (not in Lucide) MUST match the 24px viewBox + 2px stroke style.
- Icon-only buttons MUST have `aria-label` (see [accessibility.md → ARIA](../../guidelines/accessibility.md)).
- Icon color MUST resolve via `currentColor` from the parent's text color token.
