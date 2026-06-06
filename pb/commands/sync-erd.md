---
description: Generate or update the Data tab — a field / type / example table plus a Mermaid erDiagram for the prototype's eventual data model (5 guardrails — PK, FK, cardinality, naming, completeness). Decoupled and manual; never auto-fires.
---

# /pb:sync-erd

Generate the **Data** tab. **Decoupled** — only the user invokes it; never auto-fires.

## 1 · Read inputs + extract entities
`memory/spec.md` (the "Key Entities" + entity-like nouns) + `memory/plan.md` (relationships). For each
entity capture: **Name** (PascalCase singular) · **purpose** (1 line) · **attributes** (generic types
only — `identifier`, `text`, `number`, `timestamp`, `boolean`, `json`) · **relationships** (cardinality).

## 2 · Produce the Data tab content
**(a) Field / type / example table** — one row per attribute across entities:
`Entity · field · type · example · notes`.
**(b) Mermaid `erDiagram`** — entities + relationships with explicit cardinality.

## 3 · Apply the 5 guardrails
| # | Guardrail | On failure |
|---|---|---|
| 1 | Every entity has a PK | add `PK`; warn if ambiguous |
| 2 | Every FK references an existing entity | add the referenced entity as a stub; warn |
| 3 | Cardinality explicit (`\|\|--o{`, `}o--o{`, …) | default `\|\|--o{`; warn if ambiguous |
| 4 | Entity names PascalCase singular | auto-correct; warn on collision |
| 5 | All spec "Key Entities" attributes represented | add missing; warn with list |
If any failed, still write the diagram but **prepend a TODO block** listing the warnings.

## 4 · Write to the registry, then render
Produce the Data tab content as the `renderERDPopulated()` output — the field/type/example **table**,
then a `<div class="mermaid">` with the `erDiagram` (prepend the TODO block if any guardrail failed).
Write into `registry.json` → `erd`:
`{ "populated": true, "html": "<that markup>", "table": [ … ], "mermaid": "<source>", "warnings": [ … ] }`
Then `/pb:build --render`. The shell's `renderERDPopulated()` returns `erd.html`, then `renderMetaERD()` runs Mermaid.

## NEVER
- NEVER use raw SQL types (varchar/int) — use the generic set.
- NEVER auto-fire from `/pb:build` — Tab 5 is decoupled.
- NEVER suppress guardrail warnings (they go in the TODO block + the confirmation).
- NEVER omit the diagram even when guardrails fail — always write something; the warnings say what to fix.
