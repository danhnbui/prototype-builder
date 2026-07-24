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
  `renderSrc`) + anatomy/spec. Every component **MUST** carry a **`level`** (`atom` | `molecule` |
  `organism` | `template`) — it is a required field (schema 9), enforced by `lint_registry.py` (`R-LEVEL`).
  Tag it by what it composes — a primitive (button, input, heading) is an `atom`; a small cluster of atoms
  (field + label + error) is a `molecule`; a self-contained section (a sign-in card) is an `organism`.
  **DS-granularity rule:** a component that maps to a **single DS component** (`dsMatch`) is an `atom`
  even if visually composite (it lowers to one Figma INSTANCE), so don't decompose it. Build the smallest
  level that fits and compose upward (constitution principle 5 · DS rule R0.5).

> **Interactivity → confirm + declare `state`.** When the user asks for state / click / hover / any
> interaction on a component, **confirm it's interactive** and give it a `state` property (`default / …`)
> and/or the wiring (`data-action` / `data-nav` / an `onclick=` runtime helper). The design-system site
> auto-detects interactivity by that keyword — a `state` property OR body `data-*`/`onclick`/control tags —
> and gives such a component a **live, clickable demo** (others get the variant grid only). A `state`-less
> interactive component is a defect.

> **Component-first / atomic law (enforced, `R-COMPOSE` / `R-LEVEL-ORDER`, ERROR under `--strict`):**
> ONLY `atom` render bodies may emit raw HTML primitives (`<button>`, `<input>`, `<h1>`, …). Every
> `molecule` / `organism` / `template` / screen body must be **pure composition** — layout containers +
> `pbUse('<child-id>', props)` calls to lower-level components. The `pbUse` set must match the declared
> `elements[]` / `anatomy.parts[]` `orgId`s (`R-COMPOSE-MATCH`), and a level composes strictly lower levels.
> NEVER inline UI that bypasses a component (R0). NEVER spawn a second component when a variant suffices (R2).
> NEVER build a higher atomic level when a lower one composes to the same result (R0.5).

## 3 · Naming contract  (also enforced by `/pb:build-figma-handoff`)
- **`id`** — kebab-case, unique **across global and local** (R4). No collisions.
- **`renderFn`** — `renderCmp{PascalCase}` (`text-input` → `renderCmpTextInput`).
- **tokens** — every color / space / radius / shadow is a **W3C DTCG** token (`tokens.<name>` =
  `{ "$value", "$type" }`, `$type ∈ color | dimension | fontFamily | shadow | …`). No raw hex or px in a
  render body file (`renderSrc`) or `sizing`; if none fits, add a token rather than inlining a value.
  (`lint_registry.py` flags raw hex/px and non-DTCG `$type`; `--strict` makes them errors.)
- **anchors** — every element referenced by `anatomy.parts[]` or `spec.stack[]` carries a stable anchor
  class (`.field__label`, `.btn`, …) so the handoff redlines and Figma match resolve.

## 4 · Report and return
State the decision — `reuse <id>` / `variant on <id>` / `new local <id>` — plus any new tokens created,
then hand back to `/pb:build` step 4 to write the slice.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
