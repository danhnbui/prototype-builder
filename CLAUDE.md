# Product Builder v1.3.1 — router (read first)

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
| `/pb:validate` | Scaffold a Vite / Next build from `prototype.html` | P6 |
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

- **Prototype** — interactive, **no** screen-switcher. A declarative `data-*` runtime drives a real flow:
  `data-nav="<id>"` navigates; `data-action="toggle-password"`; `data-action="submit"` validates the form
  (`data-required` · `data-validate="email"` · `data-minlength`) then `data-go` / `data-toast` /
  `data-redirect`+`data-redirect-ms`. An **icon-only device switcher** (desktop ≤1180 / tablet 834 /
  mobile 390) replaces it; default from `meta.device`; one viewport, internal scroll.
- **Project Summary** & **UI Design** — share the same `meta-subtab` sub-tab component. UI Design splits
  components into **Global | Local** (by `scope`), and demos render **state variants** when a component
  declares a `state` property (interactive components MUST).
- **UX Design** — built from structured `flow.mermaid` + `flow.stories[]` (no baked HTML); left sidebar =
  **User stories | Test cases**; Mermaid uses `curve:'basis'` with legend-matched classDef colors + a legend.
- **Data** — a **Diagram | Table** toggle: diagram = `erd.mermaid`; table = one styled table per entity from `erd.table[]`.

## Memory layout (per project)

- `registry.json` — the database: `tokens`, `components` (global refs + `local`), `screens`, `meta`, `staleness`, `flow`/`erd`.
- `memory/constitution.md` — durable rules: Principles + **Stack Lock** + **DS Lock** (lean, rules-only).
- `memory/decisions.md` — the why-log (trade-offs, gate overrides).
- `design-system/{name}/{name}.md` — the global DS reference (scannable component index + rules R0–R4 + naming contract).
- `prototype.html` — rendered view, regenerated from `registry.json`.

## Schema compatibility

Write-path commands (`/pb:build`, `/pb:sync-flow`, `/pb:sync-erd`, `/pb:init --import`) apply
this check before patching `registry.json`:

1. Read `meta.schemaVersion` from `registry.json` (absent → treat as schema 2).
2. Read `CURRENT_SCHEMA` from `pb/migrations/manifest.py` (currently **3**).
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
