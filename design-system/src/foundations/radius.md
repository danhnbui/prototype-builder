# Radius Tokens

> Corner radii for controls, cards, and pills.

| Token | Value | Usage |
|---|---|---|
| `--radius-none` | 0px | Square corners (table cells, dividers) |
| `--radius-sm` | 4px | Tiny chips, code inline highlights |
| `--radius-md` | 8px | **Control radius default** (button, input, select) |
| `--radius-lg` | 12px | **Card radius default**, modal corners |
| `--radius-xl` | 16px | Hero panels, prominent containers |
| `--radius-2xl` | 24px | Large surface treatments |
| `--radius-full` | 9999px | Pills, avatars, fully-rounded badges |

## Hard rules

- Controls MUST use `--radius-md` (8px).
- Cards MUST use `--radius-lg` (12px).
- Pills MUST use `--radius-full`.
- A single component MUST NOT mix radius values (e.g., card with `--radius-md` top + `--radius-lg` bottom is forbidden).
