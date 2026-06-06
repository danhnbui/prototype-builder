# Spacing Tokens

> 4px base unit. Use ONLY these tokens — no arbitrary px values.

## Scale

| Token | Value | Usage |
|---|---|---|
| `--space-0` | 0px | No spacing |
| `--space-1` | 2px | Tight icon-to-text gaps |
| `--space-2` | 4px | Tight inline gaps (badge content) |
| `--space-3` | 8px | Small gaps, compact padding |
| `--space-4` | 12px | **Control padding default** (button, input) |
| `--space-5` | 16px | **Card padding default** |
| `--space-6` | 20px | Section internal spacing |
| `--space-7` | 24px | Section between-element gaps |
| `--space-8` | 32px | Section margins |
| `--space-9` | 40px | Major section separators |
| `--space-10` | 48px | Page-level vertical rhythm |
| `--space-12` | 64px | Hero / landing white space |
| `--space-14` | 80px | Major page sections |
| `--space-16` | 96px | Page top/bottom outer padding |

## Hard rules

- All margin, padding, gap values MUST be from this scale.
- Ad-hoc values (`margin: 13px`) are forbidden — round to the nearest token.
- For visual asymmetry that doesn't fit the scale, propose a new token and update this file. Do not inline.
