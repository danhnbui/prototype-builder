---
description: Generate or update the UX Design / Flow tab — a Mermaid wireflow diagram plus a numbered user-story test checklist. Decoupled and manual; never auto-fires.
---

# /pb:sync-flow

Generate the **UX Design · Flow** content. **Decoupled** — only the user invokes it; it never
auto-fires and runs no drift check (trio principles don't constrain flow representation).

## Pre-write schema check
Apply the **Schema compatibility** check from `CLAUDE.md` before writing to the registry. If
`meta.schemaVersion` is below `CURRENT_SCHEMA`, print the banner and suggest `/pb:migrate`. Stop
(do not write) if the current write touches a slice a pending migration changes.

## 1 · Read inputs
`memory/spec.md` (user stories, JTBDs, acceptance scenarios) + `memory/plan.md` (per-story approach,
state transitions). Invoke the `craft-connect-flow` skill for navigation / shared-state / entry-exit patterns.

## 2 · Produce ONE combined wireflow (the rules)
One Mermaid `flowchart LR` covering the whole prototype; push per-story detail into `[[Subprocess]]`
nodes. Enforced rules (each violation is a defect):
- `LR` direction; single `Start`, ≥1 `End`; no dead-ends (loop-backs OK).
- Only the 6 shapes: stadium `([…])` · rectangle `[…]` · diamond `{…?}` · parallelogram `[/…/]` ·
  subprocess `[[…]]` · cylinder `[(…)]`.
- 5–9 nodes per flow (7±2); excess → extract a subprocess, then **ASK** if still over.
- Decision labels end with `?`; every branch labeled `-- Yes -->` / `-- No -->`.
- Sentence case; verbs in actions; **no** emojis / HTML / Title Case / ALL CAPS.
- Color-coded `classDef` (start/end zinc, decision sky, action lavender, input pink, subprocess purple).
- **Wireflow nodes:** every screen-shaped node label MUST match a `registry.screens[].name`; carry
  `{ status ∈ NEW·IN PROGRESS·DONE·ATTENTION·ASAP·REVIEW·PAUSE, preview ∈ form-1·form-2·form-3·otp·success·block }`.

## 3 · User-story test checklist
A numbered list — one entry per story: `**<title> (P1)** — <JTBD>`, its **Path** through the flow, and a
`- [ ]` checkbox per acceptance scenario. This is the prototype's future **test checklist**.

## 4 · Write to the registry, then render
Produce **structured data** — not a baked HTML blob. Write into `registry.json` → `flow`:
```
{ "populated": true,
  "mermaid": "<the flowchart LR source>",
  "stories": [ { "title", "priority", "jtbd", "path", "scenarios": [ … ], "node?", "status?", "preview?" }, … ] }
```
Then `/pb:build --render`. The shell builds the tab from this data: the left sidebar has two sub-tabs —
**User stories** (title / priority / jtbd / path) and **Test cases** (one checkbox per `scenarios[]` entry) —
and the `.flow-doc-main` renders `flow.mermaid` with `curve: 'basis'` (smooth curved connectors, not zig-zag
step), classDef colors matching the on-canvas legend palette (start/end zinc · decision sky · action lavender ·
input pink · subprocess purple), a legend popover, and pan/zoom in one viewport with internal scroll.

> `flow.html` is **legacy only** — a pre-baked fallback the shell uses when `flow.mermaid` is absent. Do not
> author it; emit `mermaid` + `stories[]`.

## NEVER
- NEVER violate a flow rule (defect, not style). NEVER omit the checklist (it's what makes the tab testable).
- NEVER auto-fire from `/pb:build` or run a drift check — Tab 3 is decoupled.
- NEVER use emojis / HTML / Title Case / ALL CAPS in node labels; NEVER mix flow directions.
