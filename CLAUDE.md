# Product Builder v1.4.0 — router (read first)

Standalone, CLAUDE.md-native prototype builder. **No SpecKit** — no `extension.yml`,
`preset.yml`, or `after_*` hooks. State lives in `registry.json`; commands are native
`.claude/commands/pb:*.md` files. Full data contracts + render-function inventory live in
the playbook, [prototype-builder.md](prototype-builder.md) (authored in Phase 2).

## Commands (`/pb:*`)

| Command | Does | Lands |
|---|---|---|
| `/pb:init` | Scaffold: PRD intake (Q&A or file), set Stack + DS locks, seed `registry.json` + `memory/`; optional `--import <bundle>` | P4 |
| `/pb:specify` | Produce the spec / PRD (native) | P4 |
| `/pb:clarify` | User Insights + UI Logic Trade-offs → Project Summary; append trade-offs to `decisions.md` | P4 |
| `/pb:plan` | Implementation plan **+** per-tab task breakdown (each task: acceptance + skill) | P4 |
| `/pb:build` | The cheap loop: targeted `registry.json` patches, trio-gated, **no per-tweak render** | P3 |
| `/pb:preview` | Live preview dev server: watch `registry.json` → deterministic render → browser live-reload | P3 |
| `/pb:build-check-design-system` | *(sub)* DS-first: reuse vs extend-variant vs build-local; enforce the naming contract | P3 |
| `/pb:build-figma-handoff` | *(sub)* ported `figma-push` — 6 gates (incl. G-FP6 render audit), DS-neutral match, auto-layout, one-way | P3 |
| `/pb:sync-flow` | UX flow (Mermaid wireflow + test checklist) — decoupled, manual | P5 |
| `/pb:sync-erd` | Data (field/type/example table + Mermaid ERD) — decoupled, manual | P5 |
| `/pb:check-drift` | Read-only drift audit of the trio vs `constitution.md` | P5 |
| `/pb:hand-off` | `--people` (view-only self-documenting `prototype.html` + cover) · `--context` (portable bundle) | P6 |
| `/pb:validate` | Wrap `prototype.html` in a runnable reference build (Vite/Next) — serves the single file, not a component export | P6 |
| `/pb:migrate` | Versioned schema migration: dry-run / `--apply` / `--rollback` / `--to <N>` | P6 |

> Shipped as a Claude Code **plugin** (`pb@product-builder`, defined in `./.claude-plugin/marketplace.json` + `./pb/`) — commands invoke as `/pb:*`. After install, **restart Claude Code** to load them. (G1 decision: plugin ✓)

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
  `data-redirect`+`data-redirect-ms`. Split layout: **left** = device-framed preview (browser chrome on
  desktop, bezel+notch on tablet/mobile) with an icon-only device switcher — defaults from `meta.device`,
  sizes not in `meta.devices` are **disabled**; **right** = a structure tree (screen → component level).
- **Project Summary** — single-column; the `meta-subtab` sub-tabs (Overview · Insights · Trade-offs · Others).
- **UI Design** — split layout under a **Global | Local | Screen** control + a **design-system bar**
  (`meta.designSystem`: name + design link + code-library link, or an "add one" affordance). Global/Local
  list components by `scope`, **grouped by `level`** (atom → molecule → organism); demos render **state
  variants** when a component declares a `state` property (interactive components MUST). Clicking a
  component/screen-element opens its spec in the **persistent right aside** (anatomy/spec/UI-logic/usage).
  Components here are the **same** registry components the Prototype renders — never duplicated.
- **UX Design** — split: **left** = the `flow.mermaid` canvas (multi-flow dropdown + legend, `curve:'basis'`
  with legend-matched classDef colors); **right** = screen-size W×H inputs + **User stories | Test cases**
  from `flow.stories[]`.
- **Data** — split: **left** = a **Diagram | Table** toggle (diagram = `erd.mermaid` in the shared canvas
  wrapper; table = one styled table per entity from `erd.table[]`); **right** = relationship legend +
  clickable entities → field detail.

## Memory layout (per project)

- `registry.json` — the database: `tokens`, `components` (global refs + `local`), `screens`, `meta`, `staleness`, `flow`/`erd`. Render code is **not** here — each component/screen's `renderSrc` points at a real body file.
- `render/components/<id>.js` · `render/screens/<id>.js` — the render bodies (v1.4 schema 4): real, lintable `.js` files compiled into `prototype.html` by `render.py`. Edit these directly; the registry stays pure data.
- `memory/constitution.md` — durable rules: Principles + **Stack Lock** + **DS Lock** (lean, rules-only).
- `memory/decisions.md` — the why-log (trade-offs, gate overrides).
- `design-system/{name}/{name}.md` — the global DS reference (scannable component index + rules R0–R4 + naming contract).
- `prototype.html` — rendered view, regenerated from `registry.json`.

## Schema compatibility

Write-path commands (`/pb:build`, `/pb:sync-flow`, `/pb:sync-erd`, `/pb:init --import`) apply
this check before patching `registry.json`:

1. Read `meta.schemaVersion` from `registry.json` (absent → treat as schema 2).
2. Read `CURRENT_SCHEMA` from `pb/migrations/manifest.py` (currently **4**).
3. If `schemaVersion < CURRENT_SCHEMA`: print a one-line banner —
   `⚠ Schema gap (v<from> → v<to>): <pending migration's describe() text>. Run /pb:migrate.`
4. Proceed — **unless** the current write touches a slice a pending migration changes,
   in which case **stop** and print: `Blocked: run /pb:migrate --apply first, then retry.`

This is the canonical text. Write-path commands reference this section rather than re-stating it.
Read-only commands (`/pb:check-drift`, `/pb:preview`) and exits do **not** carry this check.

## Why (G0.5 spike, 2026-06-05)

Real-tiktoken measurement: **~3–5× cheaper over a build session + free deterministic render +
clean, deduped state** — *not* "17× per tweak." Isolated cosmetic tweaks are ~break-even; the win
is in **structural edits** and **multi-tweak sessions**, where the compact registry stays resident
in context while the HTML monolith cannot.
