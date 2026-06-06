# Shadow Tokens

> Elevation system. Four discrete levels — no inline `box-shadow`.

| Token | Value | Elevation level | Usage |
|---|---|---|---|
| `--shadow-none` | `none` | 0 | Flush surfaces |
| `--shadow-sm` | `0 1px 2px 0 rgba(0,0,0,0.05)` | 1 | Subtle controls (input rest state) |
| `--shadow-md` | `0 1px 3px 0 rgba(0,0,0,0.10), 0 1px 2px -1px rgba(0,0,0,0.06)` | 2 | **Card default**, raised buttons |
| `--shadow-lg` | `0 10px 15px -3px rgba(0,0,0,0.10), 0 4px 6px -4px rgba(0,0,0,0.05)` | 3 | Popovers, dropdowns, sticky headers |
| `--shadow-xl` | `0 20px 25px -5px rgba(0,0,0,0.10), 0 8px 10px -6px rgba(0,0,0,0.04)` | 4 | Modals, top-most floating panels |

## Hard rules

- Every elevation MUST come from a `--shadow-*` token.
- Inline `box-shadow: 0 1px 3px ...` is forbidden — it bypasses the elevation system.
- Color tints in shadows (e.g., brand-tinted shadow) require a new token, not an inline value.
