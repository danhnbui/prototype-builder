---
name: design-component-build
description: Build a new local component for Product Builder — its render body file, anatomy/spec, state variants, and token-only styling at the right atomic level. Use when /pb:build-check-design-system decides "build local" (nothing existing fits). Produces the registry entry + the render/components/<id>.js body. Not for deciding reuse-vs-build (that is /pb:build-check-design-system) or screen-level purpose (use ref-blueprint).
---

# design-component-build

Construct a new **local** component once `/pb:build-check-design-system` has ruled out reuse and variant.
The output is a registry `components[]` entry plus its render body file.

## 1 · Pick the atomic level
- **atom** — a primitive (button, input, icon).
- **molecule** — a small cluster of atoms (field = label + input + error).
- **organism** — a self-contained section (a sign-in card).
Build the **smallest** level that fits and compose upward — never an organism where a molecule + a variant
would do.

## 2 · Author the entry (data only)
- `id` — kebab-case, unique across global + local (R4).
- `renderFn` — `renderCmp{PascalCase(id)}` (e.g. `text-input` → `renderCmpTextInput`).
- `renderSrc` — `render/components/<id>.js` (create this file with the body).
- `properties[]` — including a **`state`** property if the component is interactive (options `{label,value}`).
- `anatomy`, `spec`, `uiLogic[]`, `code` — for the UI Design spec drawer.

## 3 · Write the body file (`render/components/<id>.js`)
A function body that `return`s an HTML string from `props`:
- **Tokens only** — every color/space/radius/size is `var(--token)`; no raw hex/px (`check.py` flags them).
- **State variants** — branch on `props.state` (e.g. danger border when `'error'`, spinner when `'loading'`).
- **Stable anchors** — give referenced parts anchor classes (`.btn`, `.field__input`) so specs/Figma resolve.
- Interactive markup uses the data-* runtime (see `think-logic`).

## 4 · Verify
Run `check.py` — the new id must be kebab + unique, `renderFn` must match, no raw hex/px in the body.

## Output
The new `components[]` entry + its `render/components/<id>.js` file, then hand back to `/pb:build` to write
the slice.

## Rules
- **Token-only styling** (Principle 2). **Declare `state`** for anything interactive. **Compose upward**,
  don't over-build the level.
