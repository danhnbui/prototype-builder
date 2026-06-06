# Color Tokens

> Source: shadcn-ui neutral palette (light + dark mode). Zinc base, near-black brand.

## Brand

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--brand` | `hsl(240 5.9% 10%)` | `hsl(0 0% 98%)` | Primary CTAs, active links, brand emphasis |
| `--brand-foreground` | `hsl(0 0% 98%)` | `hsl(240 5.9% 10%)` | Text/icon on `--brand` surface |
| `--brand-soft` | `hsl(240 4.8% 95.9%)` | `hsl(240 3.7% 15.9%)` | Brand-tinted backgrounds, hover fills |

## Surface

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--bg` | `hsl(0 0% 100%)` | `hsl(240 10% 3.9%)` | Page background |
| `--bg-soft` | `hsl(240 4.8% 95.9%)` | `hsl(240 3.7% 15.9%)` | Section backgrounds, zebra striping |
| `--card` | `hsl(0 0% 100%)` | `hsl(240 10% 3.9%)` | Card / panel surfaces |
| `--popover` | `hsl(0 0% 100%)` | `hsl(240 10% 3.9%)` | Popover / dropdown surfaces |
| `--border` | `hsl(240 5.9% 90%)` | `hsl(240 3.7% 15.9%)` | Borders, dividers (default weight) |
| `--border-strong` | `hsl(240 5.9% 80%)` | `hsl(240 3.7% 25%)` | Borders that need emphasis (control rest state) |

## Text

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--text-primary` | `hsl(240 10% 3.9%)` | `hsl(0 0% 98%)` | Body text, headings |
| `--text-secondary` | `hsl(240 3.8% 46.1%)` | `hsl(240 5% 64.9%)` | Captions, subheadings, secondary copy |
| `--text-tertiary` | `hsl(240 3.8% 60%)` | `hsl(240 5% 50%)` | Placeholder text, disabled labels, low-priority meta |

## Semantic

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--success` | `hsl(142 71% 45%)` | `hsl(142 70% 50%)` | Success states (toast, badge, check) |
| `--success-soft` | `hsl(142 76% 96%)` | `hsl(142 50% 12%)` | Success backgrounds |
| `--danger` | `hsl(0 84% 60%)` | `hsl(0 72% 51%)` | Error states (border, icon, toast) |
| `--danger-soft` | `hsl(0 86% 97%)` | `hsl(0 50% 16%)` | Error backgrounds |
| `--warning` | `hsl(38 92% 50%)` | `hsl(38 90% 50%)` | Warning states |
| `--warning-soft` | `hsl(48 96% 89%)` | `hsl(48 50% 18%)` | Warning backgrounds |
| `--info` | `hsl(217 91% 60%)` | `hsl(217 85% 60%)` | Info states |
| `--info-soft` | `hsl(214 100% 97%)` | `hsl(214 50% 16%)` | Info backgrounds |

## Hard rules

- Every color reference in a component spec or template MUST use one of these tokens.
- Inline `hsl()`, `rgb()`, or `#hex` values are forbidden (see [rules.md → Color](../../guidelines/rules.md)).
- A token CAN alias another (e.g., `--card: var(--bg)`) but NEVER an inline value.
