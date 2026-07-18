# Product Builder v1.8.0 — router (read first)

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
| `/pb:plan` | Implementation plan **+** per-tab task breakdown (each task: acceptance + skill + **agent · deps · slice**) | P4 |
| `/pb:orchestrate` | Dispatch `memory/tasks.md` to the agent roster in dependency **waves** — serial registry writes, render once per wave, `acceptance`-gated | P4 |
| `/pb:build` | The cheap loop: targeted `registry.json` patches, trio-gated, **no per-tweak render** | P3 |
| `/pb:preview` | Live preview dev server: watch `registry.json` → deterministic render → browser live-reload | P3 |
| `/pb:preview-ds` | Storybook-style server for the **cloned DS**: token foundations as swatches + the component catalog (read-only) | P3 |
| `/pb:test` | Sandbox testing: run scenario `test{}` blocks (functional), `--roles`, `--server`, `--security`, `--explore`; writes `lastResult` → live ✓/✗ glyphs | P3 |
| `/pb:explore` | Parallel design options: N `pb-builder` sub-agents propose alternatives → compare → keep one | P3 |
| `/pb:build-check-design-system` | *(sub)* DS-first: reuse vs extend-variant vs build-local; enforce the naming contract | P3 |
| `/pb:build-figma-handoff` | *(sub)* ported `figma-push` — 6 gates (incl. G-FP6 render audit), DS-neutral match, auto-layout, one-way | P3 |
| `/pb:flow` | UX flow (Mermaid wireflow + test checklist) — decoupled, manual | P5 |
| `/pb:data` | Data (field/type/example table + Mermaid ERD) — decoupled, manual | P5 |
| `/pb:check-drift` | Read-only drift audit of the trio vs `constitution.md` | P5 |
| `/pb:handoff-close` | Close out into one `handoff/` folder: view-only `prototype.html` + portable `bundle/` + a recipient `AGENTS.md`; `--people` / `--context` narrow to one piece | P6 |
| `/pb:validate` | Wrap `prototype.html` in a runnable reference build (Vite/Next) — serves the single file, not a component export | P6 |
| `/pb:handoff-dev` | Export at a tier — `--tier=host` (runnable prototype) · `scaffold` (deterministic React+Tailwind app) · `hardened` (idiomatic/DS-integrated — **deferred**); records `meta.outputTier` + `meta.exportTarget` | P6 |
| `/pb:update-version` | Versioned schema update: dry-run / `--apply` / `--rollback` / `--to <N>` | P6 |
| `/pb:snapshot` | History model: timestamped `registry.json` copies under `<project>/history/`; `--list` / `--restore`. Never branches, never touches host git | — |

> **Aliases (deprecated, still resolve):** `/pb:sync-flow` → `/pb:flow` · `/pb:sync-erd` → `/pb:data` · `/pb:hand-off` → `/pb:handoff-close`. The old command files are thin redirect stubs; they'll be removed in a future major release.

> Shipped as a Claude Code **plugin** (`pb@product-builder`, defined in `./.claude-plugin/marketplace.json` + `./pb/`) — commands invoke as `/pb:*`. After install, **restart Claude Code** to load them. (G1 decision: plugin ✓)

## Agent roster + sandbox (v1.5)

- **Agents** (`pb/agents/*.md`, installed to `.claude/agents/` via `tools/agents_install.py`): `pb-clarifier`, `pb-planner`, `pb-builder`, `pb-design-system`, `pb-flow`, `pb-data`, `pb-tester`, `pb-reviewer`. `/pb:orchestrate` routes each task to its fitting agent by `slice`; agents **return slice patches**, the coordinator applies them **serially** and renders **once per wave**; `pb-tester` + `pb-reviewer` are the `acceptance` gate.
- **Sandbox** (`/pb:test` → `tools/test_run.py`, Playwright — the only pip dep, isolated to this path like Node/npm at `/pb:validate`; degrades if absent): drives the `data-*` runtime to verify scenario `test{}` blocks, per-role gating, and server reachability; `tools/security_scan.py` (stdlib) scans for secrets/PII. Results write `flow.stories[].scenarios[].lastResult` (additive) → the UX-tab ✓/✗/○/☐ glyphs.
- **Roles** (all additive/optional): `meta.roles[]` + `meta.defaultRole` + `screens[].roles[]` + element `data-roles` gate the Prototype tab; a role switcher + **Reset** ride the header (kept visible to viewers even in a `--people` hand-off — only authoring controls hide); an `isAdmin` role bypasses gating.

## The three load-bearing rules (token levers — ship together)

1. **State in `registry.json`.** The loop reads/edits only the touched slice. `prototype.html`
   is **never** the source of truth and is **never** hand-edited.
2. **Batched, deterministic render.** A generator regenerates `prototype.html` from `registry.json`
   ONLY on `/pb:build --render` and automatically at `hand-off` / `validate` — **never** per tweak,
   and **never** by the model hand-emitting HTML (that is ~2–3× *worse* — measured at G0.5).
   *(`/pb:preview` may render on every change without breaking this: it's the **same generator**
   rendering **in memory** at ~0 model tokens — never the model, never written to disk unless `--write`.)*
3. **Gate-skip on non-trio tweaks.** The drift / Stack / DS gate runs only when a change touches
   the **trio** — a screen, a component, or logic. Pure cosmetic tweaks skip it.

## One preview per project

Each project has **one** preview source of truth: the live `/pb:preview` server reading that project's
`registry.json`. `prototype.html` is a derived hand-off snapshot — **never** a second preview, never
hand-edited. When an in-app preview pane is used, `/pb:preview` keeps **one** canonical
`.claude/launch.json` entry per project (`pb-preview · <folder>`) via `pb/tools/preview_register.py` —
upserted, never duplicated; entries it doesn't own are left alone.

## Tab render behaviors (the shell, `pb/template/prototype.html`)

**Unified page chrome (v1.2).** Every tab shares one layout: a `pb-page-header` (title + a `?`
**info-dialog** explaining the tab's commands/skills + an optional CTA, shown only when the tab has data),
over a `pb-content` shell — `--full` (single column, Project Summary only) or `--split` (left main · right
aside, 400–600px). When a slice is unpopulated the tab renders **only** the header + an **empty-state**
card that owns the CTA — no dead controls. (Replaces the old `meta-tag`/`meta-sub` per-tab headers.)

- **Prototype** — interactive, **no** screen-switcher. A declarative `data-*` runtime drives a real flow:
  `data-nav="<id>"` navigates; `data-action="toggle-password"`; `data-action="submit"` validates the form
  (`data-required` · `data-validate="email"` · `data-minlength`) then `data-go` / `data-toast` /
  `data-redirect`+`data-redirect-ms`. Header-line tools: a **Browser | App** chrome toggle (`meta.shell`
  default; browser = tab strip + back/reload/URL bar, app = titlebar on desktop, a contrast-aware status bar on tablet/mobile) + an icon-only device switcher
  over **4 fixed sizes** (monitor 1920×1080 · laptop 1280×832 · tablet 834×1112 · mobile 390×844), default
  from `meta.device`, sizes not in `meta.devices` **disabled**. The device-framed preview scales to fit;
  **right** = a structure tree (screen → component level).
- **Project Summary** — split: **left** = the `meta-subtab` sub-tabs (Overview · Insights · Trade-offs · Others) over a scrolling content column; **right** = a **scroll-spy table of contents** (built from the content's headings) that highlights the section in view and navigates on click. One viewport, internal scroll.
- **UI Design** — split layout under a **Global | Local | Screen** control; the **design-system bar**
  (`meta.designSystem`: name + design link + code-library link, or an "add one" affordance) sits on the
  title line. Global/Local list components by `scope`, **grouped by `level`** (atom → molecule → organism);
  each card shows **one dropdown-driven demo** (the selected variant, incl. `state`) centered, with a **Copy
  code** action on the title row. The **Screen** view auto-selects a screen and, by default, lists the
  **components used inside it** (click to open in the Component tab). Clicking a component/screen-element opens
  its spec in the **persistent right aside** — anatomy (numbered element markers + per-element token list) ·
  specification (margin/padding/gap measurement lines) · UI-logic · usage; anatomy/spec accept a **string**
  (prose) *or* a **structured object** (redlines). Components here are the **same** registry components the
  Prototype renders — never duplicated.
- **UX Design** — split: **left** = the `flow.mermaid` canvas (multi-flow dropdown + legend, straight **orthogonal**
  connectors anchored at node side-centers, nodes recolored by shape and **Yes/No branches drawn green/red**),
  filling **one viewport** — no W×H controls; **right** = **User stories | Test cases** from `flow.stories[]`.
  Hovering a story **highlights the flow path it satisfies** (matched nodes + edges, rest dimmed).
- **Data** — **single column**: a **Diagram | Table** toggle (diagram = `erd.mermaid` in the shared canvas
  wrapper, with a relationship-legend popover; table = one styled table per entity from `erd.table[]`, fixed
  column widths so all tables align). In Table view, **each entity table that has multiple data treatments
  (`erd.mock` sets) gets its own variant switcher** (Schema · its scenarios) that swaps that table's Example
  column.

## Memory layout (per project)

- `registry.json` — the database: `tokens`, `components` (global refs + `local`), `screens`, `meta`, `staleness`, `flow`/`erd`. Render code is **not** here — each component/screen's `renderSrc` points at a real body file.
- `render/components/<id>.js` · `render/screens/<id>.js` — the render bodies (v1.4 schema 4): real, lintable `.js` files compiled into `prototype.html` by `render.py`. Edit these directly; the registry stays pure data.
- `memory/constitution.md` — durable rules: Principles + **Stack Lock** + **DS Lock** (lean, rules-only).
- `memory/decisions.md` — the why-log (trade-offs, gate overrides).
- `design-system/{name}/{name}.md` — the global DS reference (scannable component index + rules R0–R4 + naming contract). Cloned by `/pb:pull-ds`; a sibling `.source.json` snapshots the source (tokens + components) for `/pb:check-drift`. `meta.dsSource` (provenance) + `meta.platform` record where it came from.
- `prototype.html` — rendered view, regenerated from `registry.json`.

## Schema compatibility

Write-path commands (`/pb:build`, `/pb:flow`, `/pb:data`, `/pb:pull-ds`, `/pb:handoff-dev`, `/pb:init --import`) apply
this check before patching `registry.json`:

1. Read `meta.schemaVersion` from `registry.json` (absent → treat as schema 2).
2. Read `CURRENT_SCHEMA` from `pb/migrations/manifest.py` (currently **7**).
3. If `schemaVersion < CURRENT_SCHEMA`: print a one-line banner —
   `⚠ Schema gap (v<from> → v<to>): <pending version update's describe() text>. Run /pb:update-version.`
4. Proceed — **unless** the current write touches a slice a pending version update changes,
   in which case **stop** and print: `Blocked: run /pb:update-version --apply first, then retry.`

This is the canonical text. Write-path commands reference this section rather than re-stating it.
Read-only commands (`/pb:check-drift`, `/pb:preview`) and exits do **not** carry this check.

## Why (G0.5 spike, 2026-06-05)

Real-tiktoken measurement: **~3–5× cheaper over a build session + free deterministic render +
clean, deduped state** — *not* "17× per tweak." Isolated cosmetic tweaks are ~break-even; the win
is in **structural edits** and **multi-tweak sessions**, where the compact registry stays resident
in context while the HTML monolith cannot.
