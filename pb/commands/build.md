---
description: The cheap build loop. Apply a targeted patch to the touched registry.json slice, trio-gated (drift/Stack/DS gate only when a screen/component/logic changes), and NEVER re-render prototype.html per tweak. Use --render to regenerate the HTML.
---

# /pb:build

The build loop. Reads/edits **only the touched slice of `registry.json`** — never the whole file,
never `prototype.html` by hand. Honors the three token levers from the project router (`CLAUDE.md`).

## Pre-write schema check
Apply the **Schema compatibility** check from `CLAUDE.md` before writing any registry slice. If
`meta.schemaVersion` is below `CURRENT_SCHEMA`, print the banner and suggest `/pb:update-version`. Stop
(do not write) if the current write touches a slice a pending version update changes.

## 0 · Flags
- `--render` — after applying the patch (or on its own), regenerate **both derived sites** from
  `registry.json` via the deterministic generator (step 5): `prototype.html` (flows/screens) **and**
  `design-system.html` (the component workbench). One registry → two projections, ~0 model tokens. This
  is the **only** way HTML is produced (besides `/pb:handoff-close` and `/pb:validate`, which render
  automatically). A component/token edit re-renders both; a screen-only edit still just re-runs the
  generator (cheap) — no need to reason about which site changed.
- no flag — apply the registry patch and **stop. Do NOT render.**

## 1 · Read the touched slice (only)
Identify the target and read ONLY that from `registry.json` — use `pb/tools/slice.py get` so
a big registry never loads whole into context:
| Prompt targets | Read |
|---|---|
| a token | `slice.py get tokens <name>` |
| a component | `slice.py get components <id>` (+ the DS index first if it's NEW — step 3) |
| a screen / element | `slice.py get screens <id>` |
| Project Summary copy | `slice.py get meta <key>` |

`slice.py list <components\|screens\|tokens\|meta>` enumerates ids/keys when you need to locate a
target first. Do not load the whole registry, and never read `prototype.html` to make an edit.

## 2 · Classify: trio or non-trio
The **trio** = a **screen**, a **component**, or **logic** (states, validation, conditional render).
- **Non-trio** — pure cosmetic: a token value, a copy reword, a prop default, a size/spacing value
  → **skip the gate** (step 3), go straight to the patch (step 4).
- **Trio** — add/restructure a screen, add/change a component, add/change logic → **run the gate**.

> NEVER run the full gate ceremony on a non-trio tweak. NEVER skip it on a trio write.

## 3 · Gate — trio writes only (ported inline drift check + DS-first)
1. **Drift.** Read `memory/constitution.md` → `## Principles`. For each principle, ask: does the
   proposed write contradict it? If any do, **PAUSE**:
   ```
   ⏸ DRIFT
   Proposed  <slice>: <one-line summary>
   Violates  #N — "<principle text>"   because <one-line reason>
   Approve override? (yes / no / revise)
   ```
   **Before you print that prompt, read what was already decided.** Grep `memory/decisions*.md`
   for the slice id being touched (and for the principle number). If a past entry covers it, show
   it above the prompt:
   ```
   ↩ ALREADY DECIDED  <date> — <title>
     Decision  <the decision line>
     ...proposing the opposite? Say so in the new entry and reference this one.
   ```
   This is not optional politeness. Three commands write this log and — until this line existed —
   none read it, which is why a real project accumulated entries marked SUPERSEDED on the same day
   they were written. The glob is `decisions*.md`, not `decisions.md`: rotation moves older entries
   to dated siblings, and a bare name silently skips them.

   On `yes` → append an entry to `memory/decisions.md` **in the template's shape** (`## <date> —
   <title>`, then `- **Decision:**`, `- **Why:**`, `- **Alternatives:**`, `- **Affects:**`). Keep the
   field names exactly as written; a grep that has to guess between `Verified` and `Verification`
   is a grep that misses. On `no/revise` → stop / adjust.
2. **Stack Lock.** Honor `memory/constitution.md` → Stack Lock. A language/framework switch needs
   explicit approval **and** a `decisions.md` entry.
3. **DS / component.** For any new or changed component, run **`/pb:build-check-design-system`**
   (DS-first: reuse → variant → local; naming contract). Invoke skills as needed:
   `think-layout` (layout), `think-logic` (state/rules), `design-component-build` (new custom component).

## 4 · Apply the targeted patch
Patch the **one** touched slice — `pb/tools/slice.py set <kind> <id>` (patch JSON on stdin) merges
into just that entry and rewrites the file, so no other slice enters context. Changed keys only:
- **token** → set `tokens.<name>.$value` (create one tagged `"scope":"local"` if none fits; never a raw hex/px elsewhere).
- **component** → patch the `components[]` entry (a `properties` default, etc.). To change
  `anatomy`/`spec`/`usage`/`uiLogic`, **edit the sidecar** `spec/components/<id>.json` (pointed at by
  `specSrc`, schema 10) — not the registry entry. To change what it renders, **edit its body file**
  `render/components/<id>.js` (pointed at by `renderSrc`). The registry holds no render code (v1.4)
  and no handoff docs (v schema 10).
- **screen** → patch the `screens[]` entry: add/zorder an element, change `layout`, a `label`, a
  `logicNotes` line. Handoff docs → `spec/screens/<id>.json`; render → `render/screens/<id>.js`.
- **new screen, and `registry.ia.jobs[]` is populated** → check whether any job's `screens[]`
  names it. If none does, say so plainly: `⚠ no declared job is served by <id> — add one to
  registry.ia.jobs[], point an existing job at it, or say why it exists.` Never block on it; a
  screen without a job is a question, not an error.
- **new component / screen** → append an entry with a **kebab-case** `id`, a `renderFn`
  (`renderCmp{PascalCase}` / `renderScreen{PascalCase}`), and a `renderSrc`
  (`render/components/<id>.js` / `render/screens/<id>.js`); create that `.js` body file with the render
  code. (A legacy inline `render` string still works but is discouraged — `lint_registry.py` warns if both are set.)

**Do not touch `prototype.html`. Do not re-render.** State what slice changed and stop (unless `--render`).

### 4a · Interactivity rules (Prototype is a real flow)
The Prototype tab is **interactive** — there is **no screen-switcher**. Wire navigation by emitting `data-*`
attributes in screen/component `render` bodies; the shell's runtime handles them:
- `data-nav="<screen-id>"` — navigate to that screen (links/buttons that move between screens).
- `data-action="toggle-password"` — show/hide the password in its `.field`.
- `data-action="submit"` — validate the enclosing form's `.field__input`s, then on success:
  `data-go="<screen-id>"` (navigate) · `data-toast="<msg>"` (toast) ·
  `data-redirect="<screen-id>"` + `data-redirect-ms="<n>"` (auto-navigate after a delay).
- input validation: `data-required` · `data-validate="email"` · `data-minlength="<n>"`.
- `data-machine="<name>"` + `data-step="<state>"` — a state machine. `data-step-pane="<state>"` panes
  show and hide with it, `data-step-go="<state>"` advances it on click, `data-step-initial` picks the
  starting state, `data-step-dot="<state>"` marks progress. For a transition a click cannot express —
  an upload that validates and then lands on either `preview` or `invalid` — call `pbSetStep(el, state)`.
  **Do not hand-roll a per-component `data-<prefix>-state` attribute and its CSS block.**
- `data-preserve` — this element's value/checked/scroll/open survives a re-render. Wrap the re-render in
  `pbPreserve(function () { … })`: it captures, re-renders, restores, then fires `input`+`change` once
  everything is back. Narrow it with `data-preserve="value scroll"`, and give it a stable `id` or
  `data-preserve-key` so it can be found again. **Do not pass a list of element ids to a re-render
  helper** — the element declares itself, which is what keeps it in step with the markup.

Two more rules:
- **Interactive components MUST declare a `state` property** (`properties[]` entry `id:'state'`, options
  `{label,value}`) — e.g. `default / error / disabled`, `default / loading / disabled`. The design-system
  site renders one labeled variant per state (and a live clickable demo for interactive ones). A
  `state`-less interactive component is a defect. Confirm interactivity with the user before you declare it.
- **`meta.device`** (`'desktop'|'tablet'|'mobile'`) sets the Prototype's default device frame. It's seeded at
  `/pb:init`; change it here only if the prototype's target form factor changes.

## 4.5 · Auto-sync the flow + erd slices (trio writes only)
A trio write changed what the product *is*, so the two slices that describe it move with it — same
turn, no Sync button, no second command. Apply the **Auto-sync** rules from `CLAUDE.md` (canonical).
Non-trio tweaks (step 2) **skip this**, exactly as they skip the gate.

**Reconcile, never regenerate.** Read the patch you just applied — not `memory/spec.md`, not
`memory/plan.md` (that is `/pb:flow` / `/pb:data`'s job, and it is the expensive one).

| The patch did | `flow` | `erd` |
|---|---|---|
| added a screen | one node in its shape + an edge per `data-nav`/`data-go`/`data-redirect` target; append a story stub (`title`/`priority`/`jtbd`/`path`/`nodes` + one `function` scenario for the happy path) | — |
| removed a screen | drop its node, repair the edges that pointed at it, drop or re-path any story whose `nodes[]` names it | — |
| renamed a screen | rename the node label; update the affected `path` strings | — |
| changed navigation | add / remove / re-point that one edge | — |
| added or changed branching logic (validation, a role gate, a conditional) | add or adjust the decision node and its `-- Yes -->` / `-- No -->` branches | — |
| added a data-bearing field | — | append its `{ entity, field, type, example, notes }` row; a new entity arrives as a **stub** (PK + this field) with a `warnings[]` line |
| removed a data-bearing field | — | drop that row |
| anything else — a component body, a prop, a label | — | — |

**Read narrowly.** `slice.py get flow mermaid` is ~15 lines and is all you need to place a node. Do
**not** pull `flow.stories[].scenarios[]` into context to append a story, and read only the touched
entity's rows out of `erd.table[]`.

### NEVER, in this step
- NEVER touch an unpopulated slice. `flow.populated` / `erd.populated` false → skip and say so in one
  line. Flipping `populated` here buries the empty-state CTA behind a one-node diagram.
- NEVER re-author. Existing `scenarios[]`, `jtbd`, priorities, coverage warnings, entities and rows stay
  exactly as written — rewriting a scenario silently discards the `lastResult` `/pb:test` wrote. No second
  five-lens QA pass. No re-running the 5 ERD guardrails across the model — guardrails 1–4 only, on the
  entity you touched only (guardrail 5 is spec-wide and stays with `/pb:data`).
- NEVER restructure. If the reconcile is bigger than an insertion — the flow would pass 9 nodes, it needs
  a new `flows[]` entry, or the entity needs relationships — **stop** and print the owning command:
  `↻ flow needs restructuring (10 nodes) — run /pb:flow`.
- NEVER render, NEVER re-gate. This writes registry slices only. The gate (step 3) already ran for the
  patch; a representation of an approved change is not a second decision.

**Say it in one line.** Wrote → `↻ synced  flow +1 node (checkout) +1 story · erd +1 field (Order.total)`.
Deferred → one line naming the command. Nothing to reconcile → **silent**.

## 4.6 · Validate the contract (advisory, after every patch)
Run the contract validator on the patched registry — **read-only, no render** (so the
token levers NS2/NS3 stay intact). From the project root:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/lint_registry.py" registry.json
```
Surface any `ERROR`/`WARN` lines to the user as advice (kebab/renderFn/orgId/token-kind
issues, a `</script>` page-killer, raw hex/px, a missing `danger` token). This is
**advisory** in the loop — it never blocks a build tweak — but the same check runs
`--strict` and **fail-closed** at `/pb:handoff-close` and `/pb:validate` before any render,
so fixing findings now avoids a blocked exit later.

## 5 · Render — batched, deterministic, on demand only
Rendering is the deterministic generator — **never** hand-write HTML (the G0.5 spike proved that is
~2–3× worse). From the project root:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/render.py" registry.json \
        "${CLAUDE_PLUGIN_ROOT}/template/prototype.html" prototype.html
```
(In-place dev tree: generator `tools/render.py`, shell `template/prototype.html`.)

If the project is at **schema 11** (it carries `logicSrc` entries), refresh the derived half of the
logic contracts in the same step — it is deterministic, costs no model tokens, and is what keeps
`seam`/`handlers`/`disclosure` from drifting off the code they describe:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/logic_extract.py" . --contracts
```
It rewrites nothing when nothing changed, and never touches the hand-authored `writes[]` /
`affordances[].why`.

## Crown-jewel rule
The render machinery (`pbRender*`, the 4-tab spec drawer, wireflow, ERD) is ported as-is and reads from
`PB_DATA`, which the shell's adapter rebuilds from `registry.json` each load. You produce **DATA**;
the generator + adapter produce the view.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
