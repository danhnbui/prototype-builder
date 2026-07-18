---
description: Generate or update the UX Design / Flow tab — a Mermaid wireflow diagram plus a numbered user-story test checklist. Decoupled and manual; never auto-fires.
---

# /pb:flow

Generate the **UX Design · Flow** content. **Decoupled** — only the user invokes it; it never
auto-fires and runs no drift check (trio principles don't constrain flow representation).

## Pre-write schema check
Apply the **Schema compatibility** check from `CLAUDE.md` before writing to the registry. If
`meta.schemaVersion` is below `CURRENT_SCHEMA`, print the banner and suggest `/pb:update-version`. Stop
(do not write) if the current write touches a slice a pending version update changes.

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
- Color-coded by shape (the shell recolors nodes to the legend palette: start/end black · decision yellow · input purple · action/screen blue · subprocess grey).
- Screen-shaped node labels SHOULD match a `registry.screens[].name` so the flow reads against the real screens.

## 3 · User-story test checklist (author as QA)
A numbered list — one entry per story: `**<title> (P1)** — <JTBD>`, its **Path** through the flow, and a
`- [ ]` checkbox per acceptance scenario. This is the prototype's future **test checklist**.

**Wear the QA hat.** For each story, write scenarios across the five lenses — tag each
`{ text, category }` with `category ∈ ux | ui | function | business | system-edge`:
- **ux** — focus order, affordances, feedback, empty/loading states.
- **ui** — visual correctness (error border AND text, tokens, responsive at the target screen size).
- **function** — the happy path + validation actually works.
- **business** — rules and policy (locked accounts, entitlements, limits).
- **system-edge** — concurrency, rate limits, timeouts, double-submit, offline.

Then list **coverage gaps** — edges your QA pass identified that the **flow/screens do not cover yet**
(a referenced-but-missing screen, an unhandled error state). Write them to `flow.coverageWarnings` as
`{ category, note }`; the tab renders them as a "Coverage gaps" callout so the user sees what to build next.

### 3a · Make a scenario executable (optional `test{}` — enables `/pb:test`)
A scenario is a manual checkbox by default (renders `☐`). To make it **runnable** by `/pb:test`, attach an
executable `test{}` block that drives the Prototype sandbox — the scenario then reports `✓` / `✗` / `○`
(pass / fail / untested) from its `lastResult` instead of `☐`:
```
{ "text": "Valid credentials land on the dashboard.", "category": "function",
  "test": { "start": "login",
            "steps": [ { "do": "fill", "target": "Email", "value": "ada@example.com" },
                       { "do": "fill", "target": "Password", "value": "hunter2hunter2" },
                       { "do": "click", "target": "submit" } ],
            "expect": [ { "screen": "dashboard" }, { "no-console-error": true } ] } }
```
- **start** — the `screens[].id` the sandbox begins on.
- **steps[].do** ∈ `fill` · `click` · `nav` · `submit` · `toggle-password` · `back`. `fill` takes `value`
  and a `target` (field label · CSS selector · `data-*` value); the rest take a `target` (selector or
  `data-*` value); `back` takes none.
- **expect[]** — each item is exactly one of `{"screen":"<id>"}` · `{"text":"..."}` ·
  `{"errors":{"min":N}}` / `{"errors":{"count":N}}` · `{"toast":"..."}` · `{"no-console-error":true}`.

Author `test{}` only where the flow is real enough to drive; leave the rest as manual checkboxes. **Do not**
author `lastResult` — `/pb:test` writes it (see the `sandbox-test` skill). This is purely additive: scenarios
without `test{}` behave exactly as before.

## 4 · Write to the registry, then render
Produce **structured data** — not a baked HTML blob. Write into `registry.json` → `flow`:
```
{ "populated": true,
  "mermaid": "<the flowchart LR source>",
  "stories": [ { "title", "priority", "jtbd", "path", "nodes": ["<mermaid-node-id>", …],
                 "scenarios": [ { "text", "category", "test"?: { "start", "steps": [ … ], "expect": [ … ] } }, … ] }, … ],
  "coverageWarnings": [ { "category", "note" }, … ] }
```
Set each story's **`path`** to its route through the flow (`"Start → Login → Dashboard"`) — hovering the
story highlights that path on the canvas. The runtime matches `path` tokens to the rendered node labels;
add **`nodes`** (the exact Mermaid node ids the story traverses, e.g. `["Start","Login","Dashboard"]`) to
make the highlight precise and robust. The canvas fills one viewport and self-fits — there are no W×H controls.
Then `/pb:build --render`. The shell builds the tab from this data: the left sidebar has two sub-tabs —
**User stories** (title / priority / jtbd / path) and **Test cases** (one checkbox per `scenarios[]` entry) —
and the `.flow-doc-main` renders `flow.mermaid` with **straight orthogonal connectors** — the shell re-routes
every edge as horizontal/vertical segments anchored at the nodes' 4 side-centers (forward edges run straight,
back-edges route under both nodes), like a Figma board (not curved or zig-zag
step). Nodes are colored by shape (start/end black · decision yellow · input purple · action/screen blue ·
subprocess grey) and the **Yes / No decision branches are drawn green / red** (with matching arrowheads).
A legend popover plus pan/zoom in one viewport with internal scroll.

> `flow.html` is **legacy only** — a pre-baked fallback the shell uses when `flow.mermaid` is absent. Do not
> author it; emit `mermaid` + `stories[]`.

## NEVER
- NEVER violate a flow rule (defect, not style). NEVER omit the checklist (it's what makes the tab testable).
- NEVER auto-fire from `/pb:build` or run a drift check — Tab 3 is decoupled.
- NEVER use emojis / HTML / Title Case / ALL CAPS in node labels; NEVER mix flow directions.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
