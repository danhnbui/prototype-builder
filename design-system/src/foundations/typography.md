# Typography Tokens

> Inter for body and headings. System font fallback chain.

## Font families

| Token | Value | Usage |
|---|---|---|
| `--font-body` | `'Inter', system-ui, -apple-system, sans-serif` | Body, captions, controls, default UI text |
| `--font-heading` | `'Inter', system-ui, -apple-system, sans-serif` | Headings, titles, prominent labels |
| `--font-mono` | `'SF Mono', Menlo, Consolas, monospace` | Code, data, technical labels |

## Type scale

| Token | Size | Line-height | Usage |
|---|---|---|---|
| `--text-xs` | 11px | 1.4 | Captions, labels, badge text |
| `--text-sm` | 12px | 1.5 | Secondary copy, helper text |
| `--text-base` | 14px | 1.55 | Body default |
| `--text-md` | 15px | 1.5 | Subheadings, emphasized body |
| `--text-lg` | 16px | 1.45 | Card titles, prominent body |
| `--text-xl` | 18px | 1.4 | Section headings (H3) |
| `--text-2xl` | 22px | 1.3 | Page subheadings (H2) |
| `--text-3xl` | 28px | 1.2 | Page headings (H1) |
| `--text-4xl` | 32px | 1.15 | Hero subheads |
| `--text-5xl` | 40px | 1.1 | Hero / landing |

## Weights

| Token | Value | Usage |
|---|---|---|
| `--font-regular` | 400 | Body text, default UI labels |
| `--font-medium` | 500 | Emphasized body, table headers |
| `--font-semibold` | 600 | Headings, button labels, prominent labels |
| `--font-bold` | 700 | Hero headings, top-level emphasis |

## Line-height shortcuts

| Token | Value | Usage |
|---|---|---|
| `--leading-tight` | 1.15 | Headings |
| `--leading-snug` | 1.3 | Subheadings, dense UI |
| `--leading-normal` | 1.5 | Body |
| `--leading-relaxed` | 1.65 | Long-form reading |

## Letter spacing

| Token | Value | Usage |
|---|---|---|
| `--tracking-tight` | -0.02em | Large headings |
| `--tracking-normal` | 0em | Body default |
| `--tracking-wide` | 0.04em | Uppercase labels, eyebrow tags |

## Hard rules

- Font size MUST be a `--text-*` token.
- Weight MUST be a semantic weight token, never a bare number.
- Line-height MUST be a `--leading-*` token.
- Headings MUST use `--font-heading`; body MUST use `--font-body`.
