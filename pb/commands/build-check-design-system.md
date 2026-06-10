---
description: Sub-command of /pb:build. Scan the global component index by function/purpose, then reuse, extend with a variant (R2), or build a local component; enforce the naming contract (kebab-case IDs, renderCmp{PascalCase}, token schema, no raw hex/px).
---

# /pb:build-check-design-system

Sub-routine of `/pb:build`. Run for **every new or changed component** before it lands in
`registry.json`. Keeps the component set DS-first and non-duplicating, and enforces the naming contract.

## 1 · Scan the index by function + purpose
Read the design system's scannable **component index** — `design-system/{name}/{name}.md`, the
`Component | renderFn | Props / variants | Purpose | Scope | Level` table. Match the NEEDED component by
**what it does**, not its name (a "Sign-in CTA" is a Button; a "code box row" is an OTP input).

## 2 · Decide — in this order
- **R0 / R1 · Reuse.** An existing component (global or local) already covers the function → reuse it;
  the screen element just points at it via `orgId`. Create nothing.
- **R2 · Variant.** An existing component covers it but needs a new state / size / style → **extend it
  with a variant** (add an option to its `properties`). Do **not** spawn a second component.
- **Build local.** Nothing fits → create a **local** component (`"scope":"local"`). Invoke
  `design-component-build` for the render body file (`render/components/<id>.js`, referenced by
  `renderSrc`) + anatomy/spec. Tag its **`level`** (`atom` | `molecule` |
  `organism`) by what it composes — a primitive (button, input) is an `atom`; a small cluster of atoms
  (field + label + error) is a `molecule`; a self-contained section (a sign-in card) is an `organism`.
  Build the smallest level that fits and compose upward — don't author an organism where a molecule + a
  variant would do (constitution principle 5 · DS rule R0.5).

> NEVER inline UI that bypasses a component (R0). NEVER spawn a second component when a variant suffices (R2).
> NEVER build a higher atomic level when a lower one composes to the same result (R0.5).

## 3 · Naming contract  (also enforced by `/pb:build-figma-handoff`)
- **`id`** — kebab-case, unique **across global and local** (R4). No collisions.
- **`renderFn`** — `renderCmp{PascalCase}` (`text-input` → `renderCmpTextInput`).
- **tokens** — every color / space / radius / shadow is a token (`tokens.<name>`),
  `kind ∈ color | radius | space | size | type`. No raw hex or px in a render body file (`renderSrc`) or
  `sizing`; if none fits, create a token tagged `"scope":"local"` rather than inlining a value.
  (`check.py` flags raw hex/px; `--strict` makes it an error.)
- **anchors** — every element referenced by `anatomy.parts[]` or `spec.stack[]` carries a stable anchor
  class (`.field__label`, `.btn`, …) so the handoff redlines and Figma match resolve.

## 4 · Report and return
State the decision — `reuse <id>` / `variant on <id>` / `new local <id>` — plus any new tokens created,
then hand back to `/pb:build` step 4 to write the slice.
