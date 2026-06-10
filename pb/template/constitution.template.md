# Constitution — {project-name}

> Durable rules for this prototype. The build loop reads this before any **trio** write
> (a screen, a component, or logic). Keep it lean — rules only, no governance ceremony.

## Principles

<!-- Numbered, falsifiable rules the drift gate checks each trio write against.
     One line each. Examples: -->
1. Error states show BOTH a danger border AND error text — never border alone.
2. One primary action per screen.
3. Every interactive element has a visible focus state.
4. All color / space / radius / shadow come from tokens — no raw hex or arbitrary px.
5. Build atomically: compose atoms → molecules → organisms → screens. A screen is assembled from
   components (each tagged `level`), never inlined one-off markup. Reuse before you build (R0/R1).

## Stack Lock

- **Language:** {language}
- **Framework:** {framework}

Locked at `/pb:init`. A switch requires explicit approval **and** a `decisions.md` entry.

## Design System Lock

- **Name:** {design-system-name}
- **Source:** {git-url | local-path | built-in}
- **Reference:** `design-system/{name}/{name}.md`

No style outside the DS tokens / components without a logged override (see `decisions.md`).

## Preview

One preview source of truth: the live `/pb:preview` server reading this project's `registry.json`.
`prototype.html` is a derived snapshot for hand-off only — never a second preview, never hand-edited.
If an in-app preview pane is used, `/pb:preview` keeps exactly one `.claude/launch.json` entry for this
project (`pb-preview · <folder>`); duplicates are pruned automatically.

## Figma Hand-off

Every export to Figma goes through `/pb:build-figma-handoff` and its gates — never hand-draw
prototype frames into Figma directly. A push is **done only when the render audit (G-FP6) passes**:
auto-layout on every frame · 0 absolutely-positioned children · 0 raw hex/px (all color, space,
radius bound to variables) · variants live in a ComponentSet · screen elements are instances. A
failing invariant blocks the contract write-back — an unverified push is never accepted as done.
