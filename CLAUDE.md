# Product Builder v1.12.0 — router (read first)

Standalone, CLAUDE.md-native prototype builder. **No SpecKit** — no `extension.yml`,
`preset.yml`, or `after_*` hooks. State lives in `registry.json`; commands are native
`.claude/commands/pb:*.md` files. Full data contracts + render-function inventory live in
the playbook, [prototype-builder.md](prototype-builder.md) (authored in Phase 2).

## Commands (`/pb:*`)

| Command | Does | Lands |
|---|---|---|
| `/pb:init` | Scaffold: PRD intake (Q&A or file), set Stack + DS locks, seed `registry.json` + `memory/`; `--import <bundle>`; **`--figma <frame>`** (resolve a Figma frame → screen, gaps → `gaps.md`, `meta.entry=figma`); **adopt-in-place** under `.prototype/` inside an existing repo | P4 |
| `/pb:pull-ds` | Clone the design system (fallback ladder: DS MCP → Figma link → code library → common) → registry tokens + `design-system/<name>/` reference + `.source.json` drift snapshot; records `meta.dsSource` + `meta.platform` | P4 |
| `/pb:specify` | Produce the spec / PRD (native) | P4 |
| `/pb:clarify` | User Insights + UI Logic Trade-offs → Project Summary; append trade-offs to `decisions.md` | P4 |
| `/pb:plan` | Implementation plan **+** per-tab task breakdown (acceptance · skill · **agent · deps · slice**) **+** first authoring of the `flow` and `erd` slices (`--flow` / `--data` / `--mock`). Routine changes need none of it — `/pb:build` reconciles both automatically | P4 |
| `/pb:orchestrate` | Dispatch `memory/tasks.md` to the agent roster in dependency **waves** — serial registry writes, render once per wave, `acceptance`-gated | P4 |
| `/pb:build` | The cheap loop: targeted `registry.json` patches, trio-gated, **no per-tweak render**. §3a is the DS-first check on every new/changed component (reuse → variant → local + the naming contract) | P3 |
| `/pb:preview` | Live preview dev server: watch `registry.json` → deterministic render → live-reload. **One server, two routes** — the prototype at `/` and the design-system workbench at `/design-system` (§2b: live demo + variant grid + Push-to-Figma + tokens) | P3 |
| `/pb:test` | **Check everything.** No flag = scenarios · roles · server · security · constitution drift · ranked health · shell coherence · DS drift, one verdict. A mode flag narrows it (`--drift` is the old `/pb:check-drift`) | P3 |
| `/pb:explore` | Parallel design options: N `pb-builder` sub-agents propose alternatives → compare → keep one | P3 |
| `/pb:handoff` | **The one hand-off command.** Asks who is receiving it: **1** everything incl. a vendored Product Builder (recipient keeps building) · **2** engineering — `prototype.html` + `design-system.html` + `logic.md` + `rules.md` + `constitution.md` · **3** Figma, lowered deterministically then written through the MCP (falls back to the DS Bridge plugin). Mode 2 tiers: `host` (a runnable Vite/Next build serving the file) · `scaffold` (React+Tailwind). One command; no sub-commands | P6 |
| `/pb:update-version` | Versioned schema update: dry-run / `--apply` / `--rollback` / `--to <N>` | P6 |

> **Retired — the files are gone, not stubbed** (see AGENTS.md §2: this needs a major bump). `/pb:flow` + `/pb:data` → `/pb:plan --flow` / `--data` (and their older `sync-` aliases) · `/pb:check-drift` → `/pb:test --drift` · `/pb:handoff-close`, `/pb:handoff-dev`, `/pb:hand-off`, `/pb:build-figma-handoff` → `/pb:handoff` · `/pb:build-check-design-system` → `/pb:build` §3a · `/pb:preview-ds` → `/pb:preview` §2b · `/pb:validate` → `/pb:handoff --tier=host`. 24 commands became 12.

> Shipped as a Claude Code **plugin** (`pb@product-builder`, defined in `./.claude-plugin/marketplace.json` + `./pb/`) — commands invoke as `/pb:*`. After install, **restart Claude Code** to load them. (G1 decision: plugin ✓)

## Agent roster + sandbox (v1.5)

- **Agents** (`pb/agents/*.md`, installed to `.claude/agents/` via `tools/agents_install.py`): `pb-clarifier`, `pb-planner`, `pb-builder`, `pb-design-system`, `pb-flow`, `pb-data`, `pb-tester`, `pb-reviewer`. `/pb:orchestrate` routes each task to its fitting agent by `slice`; agents **return slice patches**, the coordinator applies them **serially** and renders **once per wave**; `pb-tester` + `pb-reviewer` are the `acceptance` gate.
- **Sandbox** (`/pb:test` → `tools/test_run.py`, Playwright — the only pip dep, isolated to this path like Node/npm at `/pb:validate`; degrades if absent): drives the `data-*` runtime to verify scenario `test{}` blocks, per-role gating, and server reachability; `tools/security_scan.py` (stdlib) scans for secrets/PII. Results write `flow.stories[].scenarios[].lastResult` (additive) → the UX-tab ✓/✗/○/☐ glyphs.
- **Roles** (all additive/optional): `meta.roles[]` + `meta.defaultRole` + `screens[].roles[]` + element `data-roles` gate the Prototype tab; a role switcher + **Reset** ride the header (kept visible to viewers even in a `--people` hand-off — only authoring controls hide); an `isAdmin` role bypasses gating.

## The three load-bearing rules (token levers — ship together)

1. **State in `registry.json`.** The loop reads/edits only the touched slice. `prototype.html`
   is **never** the source of truth and is **never** hand-edited.
2. **Batched, deterministic render.** A generator regenerates `prototype.html` from `registry.json`
   ONLY on `/pb:build --render` and automatically at `/pb:handoff` — **never** per tweak,
   and **never** by the model hand-emitting HTML (that is ~2–3× *worse* — measured at G0.5).
   *(`/pb:preview` may render on every change without breaking this: it's the **same generator**
   rendering **in memory** at ~0 model tokens — never the model, never written to disk unless `--write`.)*
3. **Gate-skip on non-trio tweaks.** The drift / Stack / DS gate runs only when a change touches
   the **trio** — a screen, a component, or logic. Pure cosmetic tweaks skip it.

## Auto-sync — flow + erd ride the trio

The trio classifier (a screen, a component, logic) drives one more thing: after a **trio-touching**
patch, `/pb:build` reconciles the `flow` and `erd` slices **in the same turn**. No Sync button, no
second command. Non-trio tweaks — a token value, a copy reword, a prop default, spacing — **skip it**,
exactly as they skip the gate. Rule 3 is unchanged.

- **Reconcile, never regenerate.** The sync reads the patch it just applied — never `memory/spec.md`
  or `memory/plan.md`. It inserts, deletes and re-points; everything the patch did not touch is left
  exactly as authored.
- **Populated slices only.** `flow.populated` / `erd.populated` false → skip. First-time authoring is
  `/pb:plan --flow` / `--data`; they read the spec, the loop does not.
- **Never re-author.** No rewriting an existing scenario (that discards the `lastResult` `/pb:test`
  wrote), no second five-lens QA pass, no re-deriving an untouched entity.
- **Defer restructuring.** Past 9 nodes, a new flow, a new entity with relationships → stop and name
  the command that owns it. The loop inserts; it does not redesign.
- **No render, no second gate.** The sync writes registry slices only — levers 1 and 2 hold, and the
  gate already ran for the patch itself.
- **One line when it writes, one line when it defers, silent on a true no-op.**

This is the canonical text. `/pb:build`, `/pb:plan` and `/pb:orchestrate`
reference this section rather than re-stating it.

## One registry → two sites, one preview server

The registry is the single source of truth, projected into **two** deterministic sites (both built by
`/pb:build --render`, both served live by the one `/pb:preview` server, both ~0 model tokens — the token
lever): the **prototype** (`prototype.html`, `/` — flows/screens, **4 tabs**) and the **design system**
(`design-system.html`, `/design-system` — the component workbench: interactive demo + variant grid +
push-to-figma + tokens). Neither HTML file is ever hand-edited (they're derived); a component edit
re-renders both. `/pb:preview` keeps **one** canonical `.claude/launch.json` entry per project
(`pb-preview · <folder>`) via `pb/tools/preview_register.py` — **one server, two routes**; entries it
doesn't own are left alone.

## Tab render behaviors (the prototype shell, `pb/template/prototype.html` — 4 tabs)

**Unified page chrome (v1.2).** Every tab shares one layout: a `pb-page-header` (title + a `?`
**info-dialog** explaining the tab's commands/skills + an optional CTA, shown only when the tab has data),
over a `pb-content` shell — `--full` (single column, Project Summary only) or `--split` (left main · right
aside, 400–600px). When a slice is unpopulated the tab renders **only** the header + an **empty-state**
card that owns the CTA — no dead controls. (Replaces the old `meta-tag`/`meta-sub` per-tab headers.)

- **Prototype** — interactive, **no** screen-switcher. A declarative `data-*` runtime drives a real flow:
  `data-nav="<id>"` navigates; `data-action="toggle-password"`; `data-action="submit"` validates the form
  (`data-required` · `data-validate="email"` · `data-minlength`) then `data-go` / `data-toast` /
  `data-redirect`+`data-redirect-ms`; **`data-machine`/`data-step`** drives a wizard (`data-step-pane`
  shows and hides with the state, `data-step-go` advances it, `pbSetStep()` for a transition a click
  cannot express); **`data-preserve`** marks what survives a re-render (`pbPreserve(fn)` captures,
  re-renders, restores, then fires `input`+`change` once everything is back). Header-line tools: a **Browser | App | None** chrome toggle (`meta.shell`
  default; browser = tab strip + back/reload/URL bar, app = titlebar on desktop, a contrast-aware status bar on tablet/mobile, none = a flat screen with no chrome at all — tablet/mobile keep their device frame) + an icon-only device switcher
  over **4 fixed sizes** (monitor 1920×1080 · laptop 1280×832 · tablet 834×1112 · mobile 390×844), default
  from `meta.device`, sizes not in `meta.devices` **disabled**. The device-framed preview scales to fit;
  **right** = a structure tree (screen → component level).
- **Project Summary** — split: **left** = the `meta-subtab` sub-tabs (Overview · Insights) over a scrolling content column; Trade-offs moved to UX Design → Logic and `meta.others` is **deprecated** (D-30) — its tab renders only while a project still holds content there, under a banner naming the slice that now owns each kind; **right** = a **scroll-spy table of contents** (built from the content's headings) that highlights the section in view and navigates on click. One viewport, internal scroll.
- **UX Design** — split: **left** = the `flow.mermaid` canvas (multi-flow dropdown + legend, straight **orthogonal**
  connectors anchored at node side-centers, nodes recolored by shape and **Yes/No branches drawn green/red**),
  filling **one viewport** — no W×H controls; **right** = **User stories | Test cases** from `flow.stories[]`.
  Hovering a story **highlights the flow path it satisfies** (matched nodes + edges, rest dimmed).
- **Data** — **single column**: a **Diagram | Table** toggle (diagram = `erd.mermaid` in the shared canvas
  wrapper, with a relationship-legend popover; table = one styled table per entity from `erd.table[]`, fixed
  column widths so all tables align). In Table view, **each entity table that has multiple data treatments
  (`erd.mock` sets) gets its own variant switcher** (Schema · its scenarios) that swaps that table's Example
  column.

## Design system site (the shell, `pb/template/design-system.html` — served at `/design-system`)

A **second projection of the registry**, not a tab — the component home. `render.py --ds` builds it and
`serve.py` serves it beside the prototype. Every registry component is auto-collected, grouped by `scope`
→ atomic `level`. Each **interactive** component (auto-detected — a `state` property OR body
`data-*`/`onclick`/`<button>`/`<input>`) gets a **live, clickable demo**; **all** components get a
**variant grid** (the cartesian product of enum `properties`). Each component carries a **Push to Figma**
action that emits the bridge **node JSON** (`registry_to_figma.build_component_nodes`) to paste into the
plugin's *Code → Figma* tab. **Token foundations** render as swatches. The shared runtime
(`pb/template/runtime.js`, injected into both shells) renders these with the SAME `renderCmp*` functions
the prototype uses — never duplicated. (Replaces the old UI Design tab; the retired `ds_serve.py` browsed
the upstream `.source.json` clone instead of the project's live components.)

## Memory layout (per project)

- `registry.json` — the database: `tokens` (a **W3C DTCG** document — `{$value,$type}`, flat or nested-with-aliases; resolved to CSS vars by `pb/tools/tokens.py`), `components` (global refs + `local`; each carries a required atomic `level`), `screens`, `meta`, `staleness` *(deprecated — nothing writes it, and the shell stopped reading it in v1.12.0; see D-19 / D-29)*, `flow`/`ia`/`erd`, `runtime[]`. **Component-first / atomic law:** only `level:atom` render bodies emit raw HTML; molecules/organisms/screens are pure composition via `pbUse('<id>', props)` (enforced by `lint_registry.py` R-LEVEL/R-COMPOSE/R-LEVEL-ORDER, ERROR under `--strict`). Render code is **not** here — each component/screen's `renderSrc` points at a real body file.
- `render/components/<id>.js` · `render/screens/<id>.js` — the render bodies (v1.4 schema 4): real, lintable `.js` files compiled into `prototype.html` by `render.py`. Edit these directly; the registry stays pure data.
- `spec/components/<id>.json` · `spec/screens/<id>.json` — the handoff docs (**schema 10**): `anatomy`/`spec`/`usage`/`uiLogic` moved out of the registry (its bulkiest fields, ~half the file on a real project) into a sidecar per item, referenced by each entry's `specSrc`. Edit these directly; `render.py`'s `load_specs` re-inlines them into the inlined registry (hand-off / Figma-bridge metadata — the two sites render demo + grid, not a redline drawer). Do **not** re-add inline `anatomy`/`spec` to `registry.json`.
- `logic/components/<id>.json` · `logic/screens/<id>.json` — the logic contract (**schema 11**), referenced by each entry's `logicSrc`. Two halves. **Derived** — `seam`/`handlers`/`disclosure`, rewritten by `logic_extract.py --contracts`; never hand-edit them. **Hand-authored** — `writes[]` (which store slices the item mutates) and `affordances[].why`; no tool ever touches these. Static derivation traces reads but *not* writes, because the mutation happens inside a store helper, so `writes[]` is the one thing a human must state — and the Logic tab's ripple view draws it. `notes[]` holds prose migration `0009` **copied** (verbatim, with a `source` pointer) out of `logicNotes`/`uiLogic`, which are still exactly where they were.
- `runtime/*.js` — the project's own modules, declared in `registry.runtime[]` and inlined **before** every render body; an entry carrying a `url` instead of a `src` becomes a `<script src>` in the head. This is what a project uses instead of declaring a component whose render body returns `''` just to obtain a module scope.
- `memory/constitution.md` — durable rules: Principles + **Stack Lock** + **DS Lock** (lean, rules-only).
- `memory/decisions.md` — the why-log (trade-offs, gate overrides).
- `design-system/{name}/{name}.md` — the global DS reference (scannable component index + rules R0–R4 + naming contract). Cloned by `/pb:pull-ds`; a sibling `.source.json` snapshots the source (tokens + components) for `/pb:test --drift`, and `ds-catalog.json` holds the **DS Bridge Scan DS** output (portable publish keys + variables + variant/property metadata) that `registry_to_figma.py` reads for the code→Figma bridge. `meta.dsSource` (provenance) + `meta.platform` record where it came from.
- `prototype.html` — rendered view, regenerated from `registry.json`.

## Schema compatibility

Write-path commands (`/pb:build`, `/pb:plan`, `/pb:pull-ds`, `/pb:handoff`, `/pb:init --import`) apply
this check before patching `registry.json`:

1. Read `meta.schemaVersion` from `registry.json` (absent → treat as schema 2).
2. Read `CURRENT_SCHEMA` from `pb/migrations/manifest.py` (currently **11** — 8 = W3C DTCG tokens, 9 = required atomic `level` / component-first, 10 = `anatomy`/`spec`/`usage`/`uiLogic` externalized to `spec/<kind>/<id>.json` sidecars via `specSrc`, 11 = the logic contract via `logicSrc` + the `ia` slice + `registry.runtime[]`).
3. If `schemaVersion < CURRENT_SCHEMA`: print a one-line banner —
   `⚠ Schema gap (v<from> → v<to>): <pending version update's describe() text>. Run /pb:update-version.`
4. Proceed — **unless** the current write touches a slice a pending version update changes,
   in which case **stop** and print: `Blocked: run /pb:update-version --apply first, then retry.`

This is the canonical text. Write-path commands reference this section rather than re-stating it.
Read-only commands (`/pb:test --drift`, `/pb:preview`) and exits do **not** carry this check.

## Why (G0.5 spike, 2026-06-05)

Real-tiktoken measurement: **~3–5× cheaper over a build session + free deterministic render +
clean, deduped state** — *not* "17× per tweak." Isolated cosmetic tweaks are ~break-even; the win
is in **structural edits** and **multi-tweak sessions**, where the compact registry stays resident
in context while the HTML monolith cannot.
