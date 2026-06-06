# Card

> A surface for grouping related content. Use sparingly — every card on a screen creates visual weight.

## Anatomy

- container · (optional) header (title + meta + actions) · body (free content) · (optional) footer (actions)

## Properties

| Prop | Values | Default |
|---|---|---|
| `variant` | `default` / `elevated` / `outlined` / `interactive` | `default` |
| `padding` | `none` / `sm` / `md` / `lg` | `md` |

## Variants

| Variant | Background | Border | Shadow | Use case |
|---|---|---|---|---|
| `default` | `--card` | `--border` | `--shadow-none` | Most cards — content grouping with subtle delineation |
| `elevated` | `--card` | none | `--shadow-md` | Cards that should "float" — featured content, highlighted CTAs |
| `outlined` | transparent | `--border-strong` | `--shadow-none` | Minimal cards inside an already-elevated parent |
| `interactive` | `--card` | `--border` | `--shadow-none` (rest) → `--shadow-md` (hover) | Clickable cards (entire surface is the action) |

## Padding scale

| `padding` | Internal padding |
|---|---|
| `none` | 0 (caller handles spacing) |
| `sm` | `--space-4` (12px) |
| `md` | `--space-5` (16px) — **default** |
| `lg` | `--space-7` (24px) |

## Tokens consumed

- Surface: `--card` (bg), `--border` or `--border-strong` (per variant)
- Corner: `--radius-lg` (12px)
- Padding: `--space-4` / `--space-5` / `--space-7`
- Elevation: `--shadow-md` (elevated and interactive-hover variants only)
- Transition: `box-shadow 0.18s, transform 0.18s` (interactive only)

## States (interactive variant only)

| State | Visual |
|---|---|
| default | `--shadow-none`, base border |
| hover | `--shadow-md`, slight upward translate (1-2px) |
| focus | 2px focus ring (`--brand`), offset 2px outside the card |
| pressed | `--shadow-sm`, removes translate |

## Usage

- **USE** to group related content (a project listing, a form section, a stat block)
- **USE** `interactive` when the whole card is clickable (navigates somewhere)
- **USE** `elevated` for content that needs more attention than its neighbors
- **AVOID** nesting cards more than one level deep — flattens the visual hierarchy
- **AVOID** outlined cards on already-bordered backgrounds (creates double borders)
- **AVOID** `interactive` for cards with multiple actions inside — pick one or extract the actions to footer

## Header / Footer pattern

If a card has a header AND a footer, they MUST share the same horizontal padding as the body. Separator lines between sections are optional but MUST use `--border`.

```
┌─────────────────────────────────┐
│  Header (title + meta)          │  ← --space-5 padding
├─────────────────────────────────┤  ← --border separator (optional)
│                                 │
│  Body content                   │  ← --space-5 padding
│                                 │
├─────────────────────────────────┤
│  Footer (actions)               │  ← --space-5 padding
└─────────────────────────────────┘
```

## Do / Don't

✅ One card variant per visual zone
✅ Consistent padding across sibling cards
✅ Interactive cards have a clear hover signal

❌ Mixing `default` and `elevated` in the same grid (creates noise)
❌ Cards inside cards inside cards (depth confusion)
❌ Interactive cards with non-card-level actions inside (where does the click go?)

## Code reference

- HIVE component: `<Card>` (PG only)
- Shadcn equivalent: `<Card>` + `<CardHeader>` + `<CardContent>` + `<CardFooter>`
- Storybook: TBD
