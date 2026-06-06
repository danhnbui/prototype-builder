# Breakpoint Tokens

> Mobile-first responsive thresholds. Min-width based — write base styles for mobile, layer up.

## Scale

| Token | Min-width | Typical device |
|---|---|---|
| `--bp-sm` | 640px | Large phones, small tablets portrait |
| `--bp-md` | 768px | Tablets portrait |
| `--bp-lg` | 1024px | Tablets landscape, small laptops |
| `--bp-xl` | 1280px | Desktop default |
| `--bp-2xl` | 1536px | Large desktop, ultra-wide |

## Usage pattern

```css
/* Mobile-first base */
.container { padding: var(--space-4); }

/* Layer up at sm */
@media (min-width: 640px) {
  .container { padding: var(--space-6); }
}

/* Layer up at lg */
@media (min-width: 1024px) {
  .container { padding: var(--space-8); }
}
```

## Hard rules

- Media queries MUST use min-width (mobile-first), not max-width.
- Breakpoint values MUST reference the token via `var(--bp-*)` when supported, OR inline the value with a comment naming the token.
- Custom breakpoints between these tokens are forbidden — adjust the layout to fit the scale or propose a new token.
- The mobile-first base styles MUST NOT depend on a media query to work.
