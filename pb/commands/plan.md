---
description: Design the structure — the implementation plan, the per-tab task breakdown, and the first authoring of the flow and erd slices (wireflow + five-lens QA checklist; entity table + ERD with 5 guardrails). Routine changes need none of this: /pb:build reconciles flow and erd automatically on every trio write. Run this for first population and for restructuring.
---

# /pb:plan

Design the structure before anything is built: the plan, the tasks, and the two slices that describe
how the product flows and what it holds.

> **This is not a sync command.** `flow` and `erd` are reconciled **automatically** by `/pb:build` on
> every trio write (`CLAUDE.md` § *Auto-sync*) — nodes inserted, edges repaired, rows added and
> dropped, in the same turn, with no command to remember. You run `/pb:plan` for the two things the
> reconcile deliberately will not do: **first population** and **restructuring** (a new flow, a
> re-authored QA pass, a new entity with relationships, a diagram past 9 nodes). Absorbs the former
> `/pb:flow` and `/pb:data`.

## Flags
| Flag | Effect |
|---|---|
| *(none)* | Plan + tasks, then author `flow` and `erd` if either is unpopulated |
| `--flow` | Only author / restructure the `flow` slice |
| `--data` | Only author / restructure the `erd` slice |
| `--mock` | With the erd pass: also generate `erd.mock[]` data-set variants (§5c) |
| `--replan` | Re-author `memory/plan.md` + `memory/tasks.md` only; leave both slices alone |

## Pre-write schema check
Apply the **Schema compatibility** check from `CLAUDE.md` before writing to the registry. Below
`CURRENT_SCHEMA` → print the banner and suggest `/pb:update-version`. Stop (do not write) if the
current write touches a slice a pending version update changes.

---

## 1 · Plan
Invoke `ref-prd` (structured context), `think-layout` (structure), `think-logic` (state / rules). Read
`memory/spec.md` + `memory/constitution.md`. Produce `memory/plan.md`: the approach per user story,
honoring the Stack + DS locks.

## 2 · Map jobs to screens
If `registry.ia.jobs[]` is populated (seeded by `/pb:init`), fill each job's `screens[]` with the screen
ids that serve it. A job may be served by several screens, and a screen may serve several jobs — neither
is a problem.

Two outcomes are worth saying out loud in the plan rather than leaving for someone to notice:
- **A job no screen serves** is scope the plan has not covered. List it, and either plan a screen for it
  or fold it into one explicitly.
- **A screen no job points at** is a screen nobody has justified. Ask whether it is needed.

Link both directions: give each `flow.stories[]` entry a `jobs[]` list of the ids it exercises. Leave the
story's prose `jtbd` untouched — a narrative and a standing need are not the same thing.

## 3 · Task breakdown (grouped by tab)
Invoke `agent-orchestrate-tasks`. Produce `memory/tasks.md` — tasks grouped by the 4 prototype tabs
(Prototype · Project Summary · UX Design · Data) **plus the design-system site**. Each task lists:
- **acceptance** — how you'll know it's done.
- **skill** — which skill the build step invokes (`think-layout`, `think-logic`, `design-component-build`,
  `craft-connect-flow`, …).
- **agent** — which of the 8 `pb-*` agents runs it, routed by `slice`.
- **deps** — comma-separated task ids that must finish first, or `none`.
- **slice** — the one registry slice it touches: `screen` · `component` · `logic` · `tokens` · `flow` ·
  `erd` · `meta`.

These five fields are what `/pb:orchestrate` reads to dispatch each task in dependency waves. Plan a
`flow` or `erd` task **only** for work the reconcile will not do: first population, a re-authored QA
pass, a restructured diagram, a new entity's relationships. A wave carrying such a task **owns** that
slice for the wave — the reconcile stands down.

---

## 4 · Author the flow slice
Skip if `flow.populated` and nothing structural is being asked for. No drift check runs here — a flow is
a representation, not a trio decision.

**Inputs.** `memory/spec.md` (stories, JTBDs, acceptance scenarios) + `memory/plan.md`. Invoke
`craft-connect-flow` for navigation / shared-state / entry-exit patterns.

### 4a · One combined wireflow (the rules — each violation is a defect)
One Mermaid `flowchart LR` covering the whole prototype; push per-story detail into `[[Subprocess]]` nodes.
- `LR` direction; single `Start`, ≥1 `End`; no dead-ends (loop-backs are fine).
- Only the 6 shapes: stadium `([…])` · rectangle `[…]` · diamond `{…?}` · parallelogram `[/…/]` ·
  subprocess `[[…]]` · cylinder `[(…)]`.
- 5–9 nodes per flow (7±2); excess → extract a subprocess, then **ASK** if still over.
- Decision labels end with `?`; every branch labeled `-- Yes -->` / `-- No -->`.
- Sentence case; verbs in actions; **no** emojis / HTML / Title Case / ALL CAPS.
- Screen-shaped node labels SHOULD match a `registry.screens[].name`, so the flow reads against the real screens.

### 4b · The user-story test checklist (wear the QA hat)
One entry per story: `**<title> (P1)** — <JTBD>`, its **Path** through the flow, and a `- [ ]` per
acceptance scenario. Tag each `{ text, category }` with `category ∈ ux | ui | function | business | system-edge`:
- **ux** — focus order, affordances, feedback, empty/loading states.
- **ui** — visual correctness (error border AND text, tokens, responsive at the target size).
- **function** — the happy path and validation actually work.
- **business** — rules and policy (locked accounts, entitlements, limits).
- **system-edge** — concurrency, rate limits, timeouts, double-submit, offline.

Then list **coverage gaps** — edges the QA pass found that the flow/screens do **not** cover yet. Write
them to `flow.coverageWarnings` as `{ category, note }`; the tab renders them as a callout.

### 4c · Make a scenario executable (optional `test{}`)
A scenario is a manual checkbox by default (`☐`). Attach a `test{}` block to make it runnable by
`/pb:test`, and it reports `✓` / `✗` / `○` from its `lastResult` instead:
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
  and a `target` (field label · CSS selector · `data-*` value); the rest take a `target`; `back` takes none.
- **expect[]** — exactly one of `{"screen":"<id>"}` · `{"text":"..."}` · `{"errors":{"min":N}}` /
  `{"errors":{"count":N}}` · `{"toast":"..."}` · `{"no-console-error":true}`.

Author `test{}` only where the flow is real enough to drive. **Do not** author `lastResult` — `/pb:test`
writes it.

### 4d · Write it
Structured data, never a baked HTML blob. Into `registry.json` → `flow`:
```
{ "populated": true,
  "mermaid": "<the flowchart LR source>",
  "stories": [ { "title", "priority", "jtbd", "path", "jobs": ["<ia.job id>", …],
                 "nodes": ["<mermaid-node-id>", …],
                 "scenarios": [ { "text", "category", "test"?: { … } }, … ] }, … ],
  "coverageWarnings": [ { "category", "note" }, … ] }
```
Set each story's **`path`** to its route (`"Start → Login → Dashboard"`) — hovering the story highlights
that path. Add **`nodes`** (the exact Mermaid node ids) to make the highlight precise.

> `flow.html` is **legacy only** — a pre-baked fallback used when `flow.mermaid` is absent. Do not author it.

---

## 5 · Author the erd slice
Skip if `erd.populated` and nothing structural is being asked for.

### 5a · Extract entities
From `memory/spec.md` ("Key Entities" + entity-like nouns) + `memory/plan.md` (relationships). Per entity:
**Name** (PascalCase singular) · **purpose** (1 line) · **attributes** (generic types only — `identifier`,
`text`, `number`, `timestamp`, `boolean`, `json`) · **relationships** (with cardinality).

Produce **(a)** a field/type/example table — one row per attribute, `Entity · field · type · example · notes`
— and **(b)** a Mermaid `erDiagram` with explicit cardinality.

### 5b · The 5 guardrails
| # | Guardrail | On failure |
|---|---|---|
| 1 | Every entity has a PK | add `PK`; warn if ambiguous |
| 2 | Every FK references an existing entity | add the referenced entity as a stub; warn |
| 3 | Cardinality explicit (`\|\|--o{`, `}o--o{`, …) | default `\|\|--o{`; warn if ambiguous |
| 4 | Entity names PascalCase singular | auto-correct; warn on collision |
| 5 | All spec "Key Entities" attributes represented | add missing; warn with list |

If any failed, still write the diagram but **prepend a TODO block** listing the warnings.

Write into `registry.json` → `erd`:
```
{ "populated": true,
  "table": [ { "entity", "field", "type", "example", "notes" }, … ],
  "mermaid": "<the erDiagram source>",
  "warnings": [ … ] }
```

### 5c · Mock data-set variants (`--mock` only)
```
"mock": [ { "entity": "<PascalCase>", "label": "<New user|Empty|Returning|…>",
            "rows": [ { "<field>": <value>, … }, … ] }, … ]
```
Each entity renders its **own** switcher in the Table view, only when it has mock sets. Author the three
standard review scenarios per entity — **New user** (just signed up), **Empty** (0 rows → the no-data
state), **Returning** (established and populated). Row keys are the entity's field names; values are
realistic and type-appropriate. The always-present "Schema" chip shows the field/type/example definition.

> `erd.html` is **legacy only**. Do not author it; emit `table[]` + `mermaid`.

---

## Result
`memory/plan.md` + `memory/tasks.md`, and whichever of `flow` / `erd` this run authored. Then
`/pb:build --render` to see it. Next: `/pb:build` (one slice at a time) or `/pb:orchestrate` (the whole
plan in agent waves).

## NEVER
- NEVER violate a flow rule (a defect, not a style choice); NEVER omit the checklist — it is what makes
  the tab testable.
- NEVER use emojis / HTML / Title Case / ALL CAPS in node labels; NEVER mix flow directions.
- NEVER use raw SQL types (`varchar`, `int`) — use the generic set.
- NEVER suppress a guardrail warning, and never omit the diagram even when guardrails fail — write
  something; the warnings say what to fix.
- NEVER re-author a populated slice on a routine change. `/pb:build`'s reconcile owns that, and
  re-authoring discards the `lastResult` values `/pb:test` wrote.
- NEVER run a drift check here — a flow is a representation, not a trio decision.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed
> with its core intent — never silently skip the step.
