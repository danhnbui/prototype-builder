---
name: ref-design-system
description: Normalize any design-system source — a dedicated DS MCP, a Figma design-system link, a code library, or a common DS — into Product Builder's DS-export shape (tokens + component metadata + provenance). Use when cloning or re-cloning a DS — loaded by /pb:pull-ds and /pb:init's clone step. Produces the export that clone_ds.py materializes. Not for building a single component (use design-component-build) or auditing drift (that is /pb:check-drift + clone_ds.py --drift).
---

# ref-design-system

Turn a real design system into a **normalized DS-export** so pb can clone it deterministically and
later verify it hasn't drifted. Your output is one JSON object; `clone_ds.py` does the writing.

## The DS-export contract

```json
{
  "name": "<kebab-ds-name>",
  "platform": "web | ios | android | desktop",
  "source": { "type": "figma | code-library | mcp | common", "ref": "<url | path | name>" },
  "tokens": { "<kebab-name>": { "$value": "<literal>", "$type": "<dtcg-type>" }, … },
  "components": [
    { "id": "<kebab>", "level": "atom | molecule | organism",
      "variants": ["<name>", …], "purpose": "<one line>", "renderFn": "renderCmp<Pascal>" }, …
  ],
  "catalog": { /* OPTIONAL: the GHN DS Bridge "Scan DS" output verbatim — variables[], collections[],
    styles{}, components[]{key,propertyDefinitions,variants[]}. clone_ds.py writes it to
    design-system/<name>/ds-catalog.json, the PORTABLE publish-key source the code→Figma bridge
    (registry_to_figma.py) reads. Include it when the source is the plugin's Scan DS; omit otherwise. */ }
}
```

`tokens` is a **W3C DTCG** document (https://tr.designtokens.org/format/).

- **`$type`** ∈ `color · dimension · fontFamily · fontWeight · number · duration · cubicBezier · shadow · border · strokeStyle · transition · gradient · typography`. `dimension` covers space / size / radius / font-size (DTCG has no finer type). Pick the tightest fit; never leave a color as raw hex in a component — it must be a token here.
- **`$value`** is the literal (`#2563eb`, `8px`, `1.5rem`, `"Inter"`) or an **alias** `"{group.token}"` referencing another token. Keep the source's units. `$description` is optional.
- **Tiered systems stay tiered.** A DS with semantic + primitive tiers (e.g. the `ghn-ds` MCP) becomes **nested DTCG groups** with `{alias}` references (semantic → primitive) — do not flatten away the linkage; a group `$type` is inherited by its tokens. A flat map is equally valid for a flat source.
- **`level`** infers from role: a leaf (button, input, badge) = `atom`; a small composed unit (card, field, list-item) = `molecule`; a section (header, form, table) = `organism`.
- **Names are kebab-case and unique.** `renderFn` = `renderCmp` + PascalCase of the id.

## Per-source normalization

| Source (`type`) | Tokens from | Components from |
|---|---|---|
| **`mcp`** (dedicated DS MCP) | the tool's token payload — map each to a DTCG `$type`; preserve semantic→primitive tiers as nested groups + `{alias}` refs (e.g. `ghn-ds get_tokens`) | the tool's component metadata |
| **`figma`** | `get_variable_defs` (Figma variables → tokens; a variable's `resolvedType` → `$type`: COLOR→color, FLOAT→dimension/number, STRING→fontFamily) | `get_metadata` / `get_libraries` / `search_design_system` (published components → id/level/variants) |
| **`code-library`** | the repo's token source: a `tokens.json` / Style-Dictionary, CSS custom properties (`--x: …`), or a Tailwind theme | exported component names (one per component module/story) |
| **`common`** | a bundled preset's documented tokens (e.g. `built-in` / `mui`) | that preset's component list |

## Rules

- **Never invent.** A source that exposes no components yields `"components": []` — do not fabricate. Same for tokens.
- **One export, one DS.** Don't merge two systems into one export; clone them separately.
- **Provenance is exact.** `source.ref` is the literal URL / path / preset name used, so `/pb:check-drift`
  can re-fetch it and diff. Getting `ref` wrong breaks drift detection.
- **Deterministic in, deterministic out.** Given the same source state, produce the same export (ordering
  aside) so re-cloning is a no-op and drift reflects real source change, not normalization noise.
