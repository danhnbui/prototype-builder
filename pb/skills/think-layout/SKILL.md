---
name: think-layout
description: Make structural layout decisions for a Product Builder screen or component — flex vs grid, spacing rhythm, responsive behavior, z-index layering, wrap, and alignment. Use when structuring how elements are arranged — loaded by /pb:build when a screen/component changes. This is the "how to arrange" layer; ref-blueprint is the "why this screen" layer. Not for business logic (use think-logic) or cross-screen navigation (use craft-connect-flow).
---

# think-layout

Decide the structure of a render body so it is sound and token-driven. In Product Builder a render body is
the `.js` file at `renderSrc` (`render/components/<id>.js` / `render/screens/<id>.js`) — it returns an HTML
string built with **tokens only** (no raw hex/px; `lint_registry.py` flags them).

## Flex vs grid
- **Flex** for one-dimensional runs (a row of buttons, a vertical stack, a toolbar). Use `gap`, not margins.
- **Grid** for two-dimensional layouts (cards, dashboards, form columns) and when you need explicit tracks.
- Default to a single column on small screens; introduce columns only when the content needs them.

## Spacing rhythm
- Use spacing **tokens** (`var(--space-3)`, …) consistently — one scale, not ad-hoc values.
- Space *between* siblings with `gap`; pad *inside* containers with `padding`. Don't mix margin hacks.

## Responsive
- Mobile-first: design the narrow layout, then add breakpoints up.
- Respect `meta.device` / `meta.devices` — the Prototype frames the screen at that size.

## Layering & wrap
- Keep `z-index` to a small, intentional set (base · sticky · overlay · toast). Don't escalate randomly.
- Decide wrap explicitly (`flex-wrap`) for runs that can overflow; never let content clip silently.

## Output
The chosen structure for the body: container model (flex/grid), the spacing tokens, the responsive plan,
and any layering. Hand the actual markup to `design-component-build`; state logic to `think-logic`.

## Rules
- **Tokens only** — every size/space/radius is a token; create a local token before inlining a value.
- **Compose, don't nest needlessly** — the simplest structure that holds the hierarchy wins.
