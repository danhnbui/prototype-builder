---
description: Generate or update the Data tab — a field / type / example table plus a Mermaid erDiagram for the prototype's eventual data model (5 guardrails — PK, FK, cardinality, naming, completeness). Decoupled and manual; never auto-fires.
---

# /pb:data

Generate the **Data** tab. **Decoupled** — only the user invokes it; never auto-fires.

## Flags
- `--mock` — also generate `erd.mock[]` sample row-sets per entity (see step 5) so the Data Table view's
  data-set variant chips can show what data each state surfaces.

## Pre-write schema check
Apply the **Schema compatibility** check from `CLAUDE.md` before writing to the registry. If
`meta.schemaVersion` is below `CURRENT_SCHEMA`, print the banner and suggest `/pb:update-version`. Stop
(do not write) if the current write touches a slice a pending version update changes.

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
Produce **structured data** — not a baked HTML blob. Write into `registry.json` → `erd`:
```
{ "populated": true,
  "table": [ { "entity", "field", "type", "example", "notes" }, … ],
  "mermaid": "<the erDiagram source>",
  "warnings": [ … ] }
```
Then `/pb:build --render`. The shell renders a **Diagram | Table** view toggle: **Diagram** = `erd.mermaid`
(zoom/pan + the cardinality legend); **Table** = one styled `<table>` per entity (a real table component
grouped by `entity` — Field / Type / Example / Notes), not text alignment. If any guardrail failed, surface
the `warnings[]` in the confirmation (and keep the TODO block).

> `erd.html` is **legacy only** — a pre-baked fallback the shell uses when neither `erd.mermaid` nor
> `erd.table` is present. Do not author it; emit `table[]` + `mermaid`.

## 5 · Mock data / data-set variants (`--mock` only)
Write `erd.mock[]` — labeled row-sets per entity that become **data-set variant chips** in the Table view:
```
"mock": [ { "entity": "<PascalCase>", "label": "<New user|Empty|Returning|…>",
            "rows": [ { "<field>": <value>, … }, … ] }, … ]
```
Each entity renders its **own** switcher in the Table view (only when it has mock sets). Author the standard
review scenarios per entity — **New user** (a just-signed-up state), **Empty** (0 rows → the no-data state),
and **Returning** (an established, populated state). Selecting a chip swaps that table's Example column to the
scenario's values (the variant uses `rows[0]` as representative; an empty set renders the no-data dashes). Row
keys are the entity's field names (from `table[]`); values are realistic, type-appropriate examples. The
"Schema" chip (always present) shows the field/type/example definition. Decoupled — only on `--mock`.

## NEVER
- NEVER use raw SQL types (varchar/int) — use the generic set.
- NEVER auto-fire from `/pb:build` — Tab 5 is decoupled.
- NEVER suppress guardrail warnings (they go in the TODO block + the confirmation).
- NEVER omit the diagram even when guardrails fail — always write something; the warnings say what to fix.
