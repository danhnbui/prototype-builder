---
name: ref-figma-frame
description: Read a Figma frame via the Figma MCP and normalize it to Product Builder's frame-export shape (layers → DS-component ids), so /pb:init --figma can resolve it into a screen. Use when entering from a Figma frame — loaded by /pb:init --figma. Maps each layer to a design system component that ALREADY EXISTS; unmapped layers are logged to gaps.md, never invented. Not for pushing pb → Figma (that is /pb:build-figma-handoff) or cloning a whole DS (use ref-design-system).
---

# ref-figma-frame

Turn a Figma frame into a **frame-export** so `resolve_frame.py` can deterministically map it to a
screen. Your job is the read + normalize; the mapping and gap-logging are the tool's. The governing
rule is **DS fidelity at entry: map to components that already exist; never invent one.**

## The frame-export contract

```json
{
  "frame":  { "id": "<figma-node-id>", "name": "<frame name>" },
  "layers": [
    { "name": "<layer name>", "type": "<INSTANCE|FRAME|GROUP|TEXT|…>", "component": "<ds-component-id>?" }
  ]
}
```

- **`component`** (optional) — the DS component id this layer maps to, when you can resolve it. Set it
  for a Figma **component instance** whose main component matches a known DS component. Omit it when
  unsure — `resolve_frame.py` then tries a name match, and logs a gap if that fails too. **Never guess
  a `component` id that isn't in the project's DS.**
- Emit **one layer per meaningful child** of the frame (the composable units), not every nested vector.

## How to read the frame

**Preferred — GHN DS Bridge plugin (no MCP needed):** select the frame → the plugin's *Figma → Code*
tab → **Serialize selection** → paste the node JSON. `resolve_frame.py --from` accepts that
`{ meta, roots[] }` shape **directly** — it normalizes each root child to a layer and maps an
INSTANCE's `component` reference (set / name) to a known DS id. Fastest and offline.

**Fallback — Figma MCP** (context provider, when the plugin isn't available):

1. Use the Figma MCP on the frame URL/id: `get_metadata` for the layer tree + names + types,
   `get_code_connect_map` / `get_libraries` to resolve instances → published component identities.
2. For each top-level child layer, record `{ name, type }`. If it's an instance of a component that
   maps to a known DS component id (from the cloned `design-system/<name>/.source.json` or
   `registry.components[]`), set `component` to that id.
3. Write the frame-export to a temp file for `resolve_frame.py --from`.

Either way, the deterministic mapping + gap-logging is `resolve_frame.py`'s job — never invent a component.

## Rules

- **Never invent a component.** If a layer has no confident DS match, leave `component` unset — it
  becomes a `gaps.md` placeholder. A visible gap beats a fabricated component.
- **Map to what exists.** Only ids present in the project's DS are valid `component` values. When in
  doubt, omit and let the gap surface.
- **Deterministic naming.** Use the layer's real Figma name as `name`; `resolve_frame.py` kebab-cases it
  for element/screen ids, so the same frame resolves the same way each run.
- **One frame → one screen.** Don't merge multiple frames into one export; resolve them separately.
