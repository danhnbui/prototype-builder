---
description: Clone a design system into this project — resolve the DS via the fallback ladder (dedicated DS MCP → Figma design-system link → current code library → a common DS), normalize it to a DS-export, then materialize tokens + a scannable reference + a drift snapshot. Records meta.dsSource + meta.platform.
---

# /pb:pull-ds

Clone the project's design system so it becomes a **verifiable source**, not a loose label.
Resolve the DS, normalize it, and hand it to the deterministic writer.

## Pre-write schema check
Apply the **Schema compatibility** check from `CLAUDE.md` before writing to the registry.

## 1 · Resolve the source (the fallback ladder — stop at the first that applies)
Invoke the **`ref-design-system`** skill for the normalization contract (token kinds, component
levels, the naming rules). Take the source from `$ARGUMENTS` if given, else `meta.designSystem`:

1. **Dedicated DS MCP** — if a design-system MCP is connected (a tool that returns tokens +
   component metadata, e.g. `export_design_system`), call it. Search with ToolSearch first.
2. **Figma design-system link** — if the source is a `figma.com` URL (arg or
   `meta.designSystem.designLink`): use the Figma MCP — `get_variable_defs` for tokens,
   `get_metadata` / `get_libraries` / `search_design_system` for components.
3. **Current code library** — if `meta.designSystem.codeLibrary` is a local path/repo: read its
   token source (a `tokens.json`, CSS custom properties, a Tailwind/Style-Dictionary theme) and
   the component list.
4. **A common DS** — else offer a bundled common DS (e.g. `built-in` / `mui`) as a starting point,
   and tell the user they can point `/pb:pull-ds <figma-url|path>` at their real DS later.

Log which rung resolved it. **Never invent tokens or components** — if a source yields none, say so.

## 2 · Normalize to a DS-export JSON
Per `ref-design-system`, produce **one** normalized export (write it to a temp file, e.g.
`.pb-ds-export.json`):
```json
{ "name": "<ds-name>", "platform": "web|ios|android|desktop",
  "source": { "type": "figma|code-library|mcp|common", "ref": "<url|path|name>" },
  "tokens": { "<kebab-name>": { "$value": "<v>", "$type": "color|dimension|fontFamily|shadow|…" }, … },
  "components": [ { "id": "<kebab>", "level": "atom|molecule|organism",
                    "variants": [ … ], "purpose": "<one line>", "renderFn": "renderCmp<Pascal>" }, … ] }
```
`tokens` is a **W3C DTCG** document (`$value`/`$type`; `$description` optional). A tiered DS (e.g. the
`ghn-ds` MCP's semantic → primitive tiers) maps naturally to **nested DTCG groups** with `"{group.token}"`
**aliases** — keep the tiering rather than flattening it (both flat and nested are valid; `clone_ds.py` /
`tokens.py` resolve either). `clone_ds.py` still accepts a legacy `{ value, kind }` map and upgrades it.

## 3 · Materialize (deterministic)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/clone_ds.py" --from .pb-ds-export.json registry.json
```
This merges tokens into `registry.json` (additive; pass `--overwrite-tokens` to replace clashes),
sets `meta.designSystem` / `meta.platform` / `meta.dsSource`, and writes
`design-system/<name>/<name>.md` (the reference) + `design-system/<name>/.source.json` (the drift
snapshot) + — when the export carries a `catalog` (the **GHN DS Bridge Scan DS** output: publish
keys + variables + variant/property metadata) — `design-system/<name>/ds-catalog.json`, the key
source `registry_to_figma.py` reads for the code→Figma bridge. Delete the temp export after; report
the tool's summary.

## Result
A cloned DS: registry tokens seeded, a scannable `design-system/<name>/<name>.md`, provenance in
`meta.dsSource`, and a `.source.json` snapshot that `/pb:check-drift` audits against the live source.
Next: `/pb:preview-ds` to browse it, or `/pb:build` to use it.

## NEVER
- NEVER hand-edit `design-system/<name>/<name>.md` or `.source.json` — re-clone to refresh them.
- NEVER invent tokens/components a source didn't provide.
- NEVER overwrite existing project tokens silently — additive by default; `--overwrite-tokens` is explicit.

> **Skill degrade (NS6).** If `ref-design-system` or an MCP fails to load, say so and proceed with the
> core intent (a best-effort normalized export), never a silent skip.
