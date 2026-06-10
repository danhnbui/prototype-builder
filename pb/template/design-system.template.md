# {design-system-name}

> The global design-system reference for this project. The build loop reads this **DS-first** (R0)
> before creating any component. Organized by atomic layer; the **component index** is the first
> thing to scan.

## Foundations (tokens → CSS vars)

| Layer | Tokens | Notes |
|---|---|---|
| Color | `--brand`, `--brand-soft`, `--neutral-0…90`, semantic (`--bg-*`, `--text-*`, `--border*`, `--fill-*`, `--danger`, …) | every color is a token |
| Type | `--font-heading`, `--font-body`, the type scale | |
| Space | `--space-*` | |
| Radius | `--radius-sm/md/lg/full` | |
| Shadow | `--shadow-sm/md/lg` | |

Foundations map to the `tokens{}` block of `registry.json` (`{ name, value, kind }`) and are applied
onto `:root` at render. Icons: set `config.iconCdn` to your DS icon source, or leave it unset for the
inline-SVG fallback.

## Component index  ← scan this first

| Component | renderFn | Props / variants | Purpose | Scope | Level |
|---|---|---|---|---|---|
| _(one row per component in `registry.components[]`; populated by `/pb:build`)_ | | | | global / local | atom / molecule / organism |

> **Scope** = where it lives (`global` shared DS · `local` this project). **Level** = its atomic layer
> (`atom` → `molecule` → `organism`). The UI Design tab groups each scope's list by level.

## Rules

- **R0 · DS-first, Local-first.** Never inline UI that bypasses a component. Reuse a global or local
  component before building anything.
- **R0.5 · Atomic composition.** Tag every component with a `level` (`atom`|`molecule`|`organism`) and
  compose upward — atoms into molecules, molecules into organisms, organisms onto screens. Don't build an
  organism where a molecule + variants would do.
- **R1 · Reuse.** If a component covers the function, reuse it — point the screen element's `orgId` at it.
- **R2 · Variant before spawn.** Need a new state / size / style? Add a **variant** (an option on
  `properties`) — never a second component.
- **R3 · Auto-layout.** Every Figma frame uses auto-layout; no absolutely positioned children.
- **R4 · Naming.** Kebab-case `id`, unique across global + local; `renderFn` = `renderCmp{PascalCase}`.

## Naming contract  (enforced by `/pb:build-check-design-system` and `/pb:build-figma-handoff`)

- `id` — kebab-case, globally unique (no global/local collision).
- `renderFn` — `renderCmp{PascalCase}` (components) / `renderScreen{PascalCase}` (screens).
- tokens — `kind ∈ color | radius | space | size | type`; **no raw hex or px**; if none fits, create a
  token tagged `"scope":"local"`.
- anchors — a stable class on every element referenced by `anatomy.parts[]` / `spec.stack[]`.

## Local components

Components built for this project (not in the global DS) live here and are marked `"scope":"local"` in
`registry.json`. Promote one to global only when it's reused across prototypes.
