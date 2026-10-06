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
  is the **only** way HTML is produced (besides `/pb:handoff` and `/pb:handoff --tier=host`, which render
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

## 1b · Responsive — ask once, before the first trio write that needs it
Read `meta.responsive` and `meta.devices`. Group the devices by size class — **compact** (mobile) ·
**medium** (tablet) · **expanded** (laptop, monitor).
- **`null` and two or more classes** (an older project, or an init that skipped it) → **stop and ask
  before any screen or component write**, naming the sizes: *"Should the UI adapt to each of these
  devices — its own layout on <sizes> — or keep one layout for <meta.device>?"* Record the answer exactly
  as `/pb:init` §3 does (`true`, or `false` plus trimming `meta.devices` to `[meta.device]`), with a
  Principle and a `decisions.md` line. Ask **once** — never again once it is recorded.
- **`true`** → every new or restructured screen/component in this run is built for every listed size
  (`CLAUDE.md` → *Responsive across devices*). **Yes means build it now**, not later: a screen that
  only works at `meta.device` is unfinished.
- **`false`, or one class** → one layout at `meta.device`; nothing more to do.
- Non-trio tweaks never trigger the question.

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
3. **DS / component.** For any new or changed component, run **§3a** below — DS-first: reuse →
   variant → local, then the naming contract. Invoke skills as needed: `think-layout` (layout),
   `think-logic` (state/rules), `design-component-build` (a new custom component).
   For a new or restructured screen or component, `think-layout` §2–§3 (a component chosen per region,
   the density budget) and §5 (render it and look at both widths) are not optional — a layout handed
   back without them is unfinished, and §5 with no browser is reported blocked, never passed. Look with
   `shot.py` — `python3 "${CLAUDE_PLUGIN_ROOT}/tools/shot.py" registry.json --screen <id> [--viewport WxH]…` —
   never a hand-written Playwright script (`CLAUDE.md` § *pb bounds its own footprint*).
   With **`meta.responsive: true`**, `think-layout` §4 *Responsive* is part of that: each size class
   in `meta.devices` gets its own answer (navigation, columns, table → cards, dialog → sheet), written
   as container queries in the item's `styleSrc` sheet or with the `r-*` utilities, and §5 looks at
   **every** listed size, not two. A screen that is the phone layout stretched to 1280px fails.

### 3a · DS-first check (every new or changed component)

Keeps the component set DS-first and non-duplicating. Absorbs the former
`/pb:build-check-design-system`, which was only ever reachable from here.

**Scan the index by function + purpose.** Read the design system's component index —
`design-system/{name}/{name}.md`, the `Component | renderFn | Props / variants | Purpose | Scope | Level`
table. Match by **what it does**, not what it is called: a "Sign-in CTA" is a Button; a "code box row"
is an OTP input.

**Then decide, in this order:**
- **R0 / R1 · Reuse.** An existing component (global or local) already covers the function → reuse it;
  the screen element points at it via `orgId`. Create nothing.
- **R2 · Variant.** It covers the function but needs a new state / size / style → **extend it with a
  variant** (add an option to its `properties`). Do **not** spawn a second component.
- **Build local.** Nothing fits → create a **local** component (`"scope":"local"`). Invoke
  `design-component-build` for the render body (`render/components/<id>.js`, referenced by `renderSrc`)
  + anatomy/spec — its §2 states × variants checklist is filled before the entry is written, not after.
  `lint_registry.py --strict` now carries `R-PROP-DECLARED` (a `props.X` the body reads that
  `properties[]` does not declare) and `R-PROP-USED` (a declared option the body never renders; for
  `state`, a fake interactive state), and a new component is run once with `lint_registry.py --exec`,
  which executes the body in node and fails a throw, a non-string or an empty string.
  Every component **MUST** carry a **`level`** (`atom` | `molecule` | `organism` |
  `template`) — required since schema 9, enforced by `R-LEVEL`. Tag it by what it composes: a primitive
  (button, input, heading) is an `atom`; a small cluster (field + label + error) is a `molecule`; a
  self-contained section (a sign-in card) is an `organism`.
  **DS-granularity rule:** a component mapping to a **single DS component** (`dsMatch`) is an `atom`
  even when visually composite — it lowers to one Figma INSTANCE — so don't decompose it. Build the
  smallest level that fits and compose upward (constitution principle 5 · DS rule R0.5).

> **Interactivity → confirm + declare `state`.** When the user asks for state / click / hover / any
> interaction, **confirm it is interactive** and give it a `state` property (`default / …`) and/or the
> wiring (`data-action` / `data-nav` / an `onclick=` runtime helper). **Every listed component gets a
> live, clickable demo** on the design-system site — interactivity does not decide that. What it
> decides is whether the demo can be *driven*: the `state` property is what puts each state in the
> variant picker and the Variants & spec tab, and the wiring is what makes the demo respond. A
> `state`-less interactive component is a defect: its states can be neither picked nor shown.

> **Component-first / atomic law** (enforced by `R-COMPOSE` / `R-LEVEL-ORDER`, ERROR under `--strict`):
> ONLY `atom` render bodies may emit raw HTML primitives (`<button>`, `<input>`, `<h1>`, …). Every
> `molecule` / `organism` / `template` / screen body is **pure composition** — layout containers plus
> `pbUse('<child-id>', props)` calls to lower levels. The `pbUse` set must match the declared
> screen `elements[]` `orgId`s and a component's `instance` parts — `anatomy` `instanceOf` (`R-COMPOSE-MATCH`), and a level composes strictly lower
> levels. NEVER inline UI that bypasses a component (R0). NEVER spawn a second component when a
> variant suffices (R2). NEVER build a higher level when a lower one composes to the same result (R0.5).

**Naming contract** (also enforced at `/pb:handoff` mode 3):
- **`id`** — kebab-case, unique **across global and local** (R4). No collisions.
- **`renderFn`** — `renderCmp{PascalCase}` (`text-input` → `renderCmpTextInput`).
- **tokens** — every color / space / radius / shadow is a **W3C DTCG** token (`tokens.<name>` =
  `{ "$value", "$type" }`). No raw hex or px in a render body or `sizing`; if none fits, add a token
  rather than inlining a value. (`lint_registry.py` flags raw hex/px and non-DTCG `$type`; `--strict`
  makes them errors.)
- **parts** — every meaningful element in an atom's body carries `data-part="<name>"` (kebab; the root is
  `data-part="root"`); a `pbUse` child needs none — it is measured as an `instance` part of its id. This is
  what `spec_measure.py` reads (below) and what the design-system site's Anatomy and Spec draw on.

**Measure the spec — when a component is built or changed** (not on reuse, not on a token or copy tweak,
never per page load). After the body file is written, run:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/spec_measure.py" --registry registry.json --component <id> --write
```
It renders the component with its demo props, reads padding, margin, item spacing, radius and colours per
`data-part`, maps each value to a token only when it equals one, derives optional parts (`visibleWhen`) by
re-rendering with each prop unset, and writes `anatomy`/`layout`/`elements`/`shape`/`measured` into
`spec/components/<id>.json` (adding `specSrc` if absent). Never hand-edit those five keys. The page it
measures on carries `product.css` and the component's `styleSrc` sheet and its stage is a `pb-screen`
container, so a responsive component is measured with its own sheet, at the width `--width N` names
(default by `meta.device`: mobile 375 · tablet 768 · anything else 960 — one size class per run).
It writes under the registry lock, replaces each sidecar atomically, and never writes over a sidecar that is
not valid JSON (it reports the file and leaves it as it is).

It exits with one code per cause — read the code, do not guess:

| Exit | Meaning | What to do |
|---|---|---|
| 0 | measured (and written, with `--write`) | continue to §4 |
| 1 | a component could not be measured or written: its body threw or returned nothing on its demo props, the id does not exist, or its sidecar is not valid JSON (stderr names which). The other components were still done | fix that component before §4 |
| 2 | Playwright is not installed — this code means that and nothing else | say so in one line (`spec not measured — Playwright not installed`) and continue |
| 3 | Chromium cannot be launched | say so in one line (`spec not measured — Chromium missing; playwright install chromium`) and continue |
| 4 | `registry.json`, a spec sidecar it names, or a render body could not be read | fix the file stderr names, then run it again |
| 5 | the measuring page did not load (a `runtime/*.js` module cannot be parsed) | fix the module stderr names, then run it again |
| 6 | `--write` refused: `registry.json` is below schema 13 | run `/pb:update-version --apply` first (the schema check), then measure |
| 7 | `--write` refused: another pb process holds `registry.json.lock` | wait a few seconds and run it again; it clears by itself |

**Report the decision** — `reuse <id>` / `variant on <id>` / `new local <id>` — plus any new tokens
created, then continue to §4.

## 4 · Apply the targeted patch
Patch the **one** touched slice — `pb/tools/slice.py set <kind> <id>` (patch JSON on stdin) merges
into just that entry and rewrites the file, so no other slice enters context. Changed keys only:
- **token** → set `tokens.<name>.$value` (create one tagged `"scope":"local"` if none fits; never a raw hex/px elsewhere).
- **component** → patch the `components[]` entry (a `properties` default, etc.). To change
  `usage`/`uiLogic`/the notes, **edit the sidecar** `spec/components/<id>.json` (pointed at by
  `specSrc`, schema 13) — not the registry entry; its `anatomy`/`layout`/`elements`/`shape`/`measured` are
  measured (§3a), never hand-edited. To change what it renders, **edit its body file**
  `render/components/<id>.js` (pointed at by `renderSrc`). The registry holds no render code (v1.4)
  and no handoff docs (schema 10 moved them to sidecars).
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
- **responsive rules** → a `styleSrc` sheet, `render/styles/<id>.css`, beside the body: the body puts
  `c-<id>` (component) or `s-<id>` (screen) on its root element, the sheet styles that class with
  `@container pb-screen (min-width: …)` — **never `@media`**, which answers the browser window, not the
  device frame. Anything that changes across sizes goes in the sheet, never inline (an inline
  declaration beats the container rule). Tokens only. Contract: `prototype-builder.md` → *Responsive styles*.

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
  site offers each state in the variant picker and renders one labeled variant per state in Variants & spec. A
  `state`-less interactive component is a defect. Confirm interactivity with the user before you declare it.
- **The project's name, design-system name and Figma file** (`meta.name`, `meta.designSystem.name`,
  `meta.designSystem.designLink`) are edited in the **Project settings** dialog when `/pb:preview` serves
  the page. Opened read-only (over `file://`, or in a hand-off) the dialog hands out a **plain prompt** to
  paste here — `Set this project's name to "…"`, `Set this project's design system name to "…"`,
  `Set this project's Figma file link to "…"` — so treat that sentence as the request. It is a `meta` patch
  (`slice.py set meta <key>`: `name`, `designSystem.name`, `designSystem.designLink`), not a trio change, so
  no gate and no render. Apply the dialog's own rules: neither name may be empty, a Figma link must be a
  `figma.com/file/…` or `figma.com/design/…` link (an empty one removes the key), and no value may carry a
  control or invisible character. There is no `/pb:build set …` syntax.
- **`meta.device`** (`'monitor'|'laptop'|'tablet'|'mobile'`) sets the Prototype's default device frame and
  **`meta.responsive`** whether the UI adapts across `meta.devices`. Both are seeded at `/pb:init`; change
  them here only if the target form factor changes (and say so in `decisions.md`).

## 4.5 · Auto-sync the flow + erd slices (trio writes only)
A trio write changed what the product *is*, so the two slices that describe it move with it — same
turn, no Sync button, no second command. Apply the **Auto-sync** rules from `CLAUDE.md` (canonical).
Non-trio tweaks (step 2) **skip this**, exactly as they skip the gate.

**Reconcile, never regenerate.** Read the patch you just applied — not `memory/spec.md`, not
`memory/plan.md` (that is `/pb:plan --flow` / `/pb:plan --data`'s job, and it is the expensive one).

| The patch did | `flow` | `erd` |
|---|---|---|
| added a screen | one node in its shape + an edge per `data-nav`/`data-go`/`data-redirect` target; append a story stub (`title`/`priority`/`jtbd`/`path`/`nodes` + one `function` scenario for the happy path) | — |
| removed a screen | drop its node, repair the edges that pointed at it, drop or re-path any story whose `nodes[]` names it | — |
| renamed a screen | rename the node label; update the affected `path` strings | — |
| changed navigation | add / remove / re-point that one edge | — |
| added or changed branching logic (validation, a role gate, a conditional) | add or adjust the decision node and its `-- Yes -->` / `-- No -->` branches | — |
| changed logic an `ia.rules[]` rule describes (its `implementedBy` / `displayedIn` names the touched item) | — | — · and patch that rule's matching `blocks[]` entry (a `cases` row, a `params` value, a `validation` message) — or create the block when the rule has none — so the Logic tab still says what the code does, not only its prose. Then run `python3 "${CLAUDE_PLUGIN_ROOT}/tools/logic_shape.py" registry.json --rule <id> --json` on each touched rule and author what it suggests from facts the change already stated Never rewrite its `decision{}` — a changed decision is `/pb:clarify` |
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
  entity you touched only (guardrail 5 is spec-wide and stays with `/pb:plan --data`).
- NEVER restructure. If the reconcile is bigger than an insertion — the flow would pass 9 nodes, it needs
  a new `flows[]` entry, or the entity needs relationships — **stop** and print the owning command:
  `↻ flow needs restructuring (10 nodes) — run /pb:plan --flow`.
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
`--strict` and **fail-closed** at `/pb:handoff` and `/pb:handoff --tier=host` before any render,
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
