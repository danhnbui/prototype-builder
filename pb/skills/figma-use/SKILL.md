---
name: figma-use
description: Authoring rules for the GHN DS Bridge code→Figma bridge — how to emit / edit valid declarative node JSON that the plugin rebuilds as real, linked component instances. Loaded by /pb:build-figma-handoff Step 6. The transformer (registry_to_figma.py) emits this deterministically; use this skill when hand-editing the emitted JSON or authoring a piece by hand. Real keys/variants/props only, prefer tokens, instances as references, auto-layout everywhere, flag gaps — never invent. DS-neutral. (A legacy Figma-MCP write path is retained behind --mcp; its rituals are in the appendix.)
---

# figma-use — GHN DS Bridge node-JSON authoring

The **bridge** puts prototype content into Figma by exchanging **declarative node JSON** with the GHN
DS Bridge plugin: pb emits it (deterministically, via `registry_to_figma.py`), you paste it into the
plugin's **Code → Figma** tab, and the plugin rebuilds it as real, **linked component instances**. This
skill is the authoring contract for that JSON — for when you hand-edit the emitted `figma-nodes.json`
or author a fragment. The transformer already follows these rules; keep them intact when you touch it.

## DS-neutral rule
Never write a literal design-system name. Read it from `memory/constitution.md` → Design System Lock,
mirrored as `figma-transfer.json.dsMatch.library`. Everywhere below, `{DS}` = that value.

## Node JSON — the shape you emit
`{ meta, roots: [ <node> ] }`. A `<node>`:
- `type` — `FRAME | COMPONENT | INSTANCE | TEXT | …`; `name`.
- `layout` — `{ mode: HORIZONTAL|VERTICAL, itemSpacing, paddingTop/Right/Bottom/Left, primaryAxisAlignItems, counterAxisAlignItems, primaryAxisSizingMode, counterAxisSizingMode, layoutWrap }`.
- `sizingH` / `sizingV` — `FILL | HUG | FIXED` (relative to the parent auto-layout).
- `fills` / `strokes` — a variable-bound paint `{ paints:[…], token, tokenId, tokenKey }`, a `{ styleRef }`, or a raw paint + `untokenized:true`.
- `cornerRadius` — a number **and/or** a `{ token, id, key }` (pb emits number + a `cornerRadiusToken` sidecar).
- spacing token sidecars — `itemSpacingToken` / `padding<Side>Token` = `{ token, id, key }` (number stays for fallback).
- `children[]` — nested nodes (a FRAME's real content; an INSTANCE's children are read-only context, ignored on rebuild).
- **INSTANCE** — `component: { set, key, variant } | { name, key }` + `componentProperties: { "<PropName>": value, … }`. Rebuilt from `component.key`; children ignored.

## The five rules (from AGENT_GUIDE — keep them intact)

1. **Real keys / variants / props only.** Every `component.key`, `variant` value, and property name
   must come from a **serialized node or the Scan DS catalog** (`design-system/<name>/ds-catalog.json`).
   NEVER invent a key or a `#nodeid` prop. `registry_to_figma.py` resolves keys from
   `figma-transfer.json.dsKey` then the catalog — no fuzzy guessing beyond name/dsMatch.
2. **Prefer tokens.** If a color/space/radius has a `token`/`styleRef`/`{token,id,key}` ref, keep it.
   NEVER replace a token ref with a raw hex/px. An unmapped value stays raw **plus** `untokenized:true`
   (a visible gap), never silently baked.
3. **Instances are references.** To place a component, emit an `INSTANCE` with `component` +
   `componentProperties` — do NOT hand-build its internals as frames/text. This is the whole point:
   the rebuilt node stays linked to the real `{DS}` component. A screen element → one INSTANCE.
4. **Respect auto-layout (R3).** Set `layout` on every container (`mode ≠ NONE`) and `sizingH`/`sizingV`
   on children — NEVER absolute `x`/`y`. Padding/`itemSpacing` come from spacing **tokens** (number +
   `*Token` sidecar). A child that can't be expressed as auto-layout is a gap to surface, not an
   absolute-position fallback.
5. **Flag gaps, don't fake them.** If a component/token you need isn't in the source or the catalog,
   emit the honest fallback (a local FRAME from anatomy / `untokenized` raw value) **and** record it in
   `gaps.md` + `meta.gaps` / the `gaps[]` array. Say what's missing; never fabricate a reference.

## Component-first / atomic (why the tree lowers cleanly)
The registry is a composition tree: only atoms hold primitives; molecules/organisms/screens compose
lower components (lint R-COMPOSE). So each element/part is already a component reference → it lowers 1:1
to an INSTANCE. If you find yourself hand-building a primitive frame where a catalog component exists,
stop — that is the anti-pattern the whole bridge avoids.

## Round-trip self-check (you are blind to the built result)
After the user pastes + Builds, verify by serializing the built frame back (plugin *Figma → Code*) and
diffing against what you emitted. Assert: every intended element is an **INSTANCE** with a
`mainComponent` (not a detached copy); every fill/spacing/radius that had a token ref is **bound to a
variable** (needs the plugin patch in `docs/figma-bridge-plugin.md` for spacing/radius); auto-layout on
every frame; declared gaps are the only unresolved items. Any miss → report it; do not declare done.

## NEVER
- NEVER invent a `component.key`, variant value, or property name — real ones only (catalog / serialized).
- NEVER replace a token ref with a raw value; an unmapped value is `untokenized` + a gap.
- NEVER hand-build an instance's internals — emit `component` + `componentProperties`.
- NEVER emit absolute positioning — auto-layout on every frame, sizing on children.
- NEVER fabricate to fill a gap — flag it in `gaps.md`.
- NEVER hardcode a design-system name — resolve `{DS}` from config.
- NEVER reconcile Figma → registry here (that's `/pb:init --figma` / `ref-figma-frame`); this is one-way.

---

## Appendix — legacy Figma-MCP write path (`--mcp`, deprecated)
When `/pb:build-figma-handoff --mcp` is used (no plugin available), writes go through the Figma MCP
`use_figma` instead of the node-JSON paste. The old fail-closed rituals apply: auto-layout on every
created frame; bind every fill/stroke/spacing/radius/type to a Figma **variable** (never raw); name
variants `prop=value` then `combineAsVariants` into a `ComponentSet`; images as an `ImagePaint` fill on
a shape (`createImage`/`createImageAsync`); icons via `createNodeFromSvg`; and a **read-back self-check**
(`get_metadata`/`get_screenshot`) after every write — re-read and assert auto-layout, zero raw values,
ComponentSet variants, non-empty image fills, and dsMatch elements as instances. This path is retained
for parity only; the declarative bridge above is the default and preferred route.
