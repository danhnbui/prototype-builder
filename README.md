# Product Builder v1.2.0

A standalone, CLAUDE.md-native prototype builder for Claude Code. Turn a PRD into an interactive,
self-documenting **5-tab prototype** — with a cheap build loop, a small memory layer, and a
**design-system-agnostic** core. State lives in a compact `registry.json`; `prototype.html` is a
rendered view, regenerated deterministically (so the build loop edits tens of lines of JSON, not a
3,600-line file).

## Install (it's a Claude Code plugin)

```
/plugin marketplace add ./
/plugin install pb@product-builder
```

Restart Claude Code — the commands appear as `/pb:*`. (User-scope; the commands are global, per-project
state stays in each prototype's folder.)

## Commands

| Command | Does |
|---|---|
| `/pb:init` | Scaffold: PRD intake (Q&A or file), set Stack + DS locks, seed `registry.json` + `memory/`; `--import` a bundle |
| `/pb:specify` | Produce the spec / PRD |
| `/pb:clarify` | User Insights + UI Logic Trade-offs → Project Summary; append to `decisions.md` |
| `/pb:plan` | Implementation plan + per-tab task breakdown (acceptance + skill) |
| `/pb:build` | The cheap loop: targeted `registry.json` patches, trio-gated, no per-tweak render; `--render` to view |
| `/pb:preview` | Live preview dev server: watch `registry.json` → render → live-reload the browser |
| `/pb:build-check-design-system` | DS-first reuse → variant → local + naming contract |
| `/pb:build-figma-handoff` | One-way registry → Figma (5 gates, DS-neutral, auto-layout) |
| `/pb:sync-flow` | UX Design / Flow — wireflow + test checklist (decoupled) |
| `/pb:sync-erd` | Data — field/type/example table + ERD (decoupled) |
| `/pb:check-drift` | Read-only drift audit of the trio vs the constitution |
| `/pb:hand-off` | `--people` (view-only) · `--context` (portable bundle) |
| `/pb:validate` | Scaffold a Vite / Next build from `prototype.html` |

## Quickstart

1. `/pb:init` — intake a PRD, set the locks, seed the project.
2. `/pb:specify` → `/pb:clarify` → `/pb:plan` — shape the spec, insights, and tasks.
3. `/pb:build` — build the prototype; `/pb:build --render` to regenerate `prototype.html`.
4. `/pb:sync-flow` / `/pb:sync-erd` — populate the UX Design and Data tabs (on demand).
5. `/pb:hand-off --people` — a view-only artifact to share; `--context` to hand to another builder.
6. `/pb:validate` — a real Vite/Next build when you're ready to graduate to an app.

## Under the hood

- **`registry.json`** is the single source of truth (tokens, components, screens, meta, flow, erd, config).
- **`prototype.html`** renders from it via a deterministic generator (`pb/tools/render.py`) + a thin
  adapter onto the ported render machinery — never hand-edited.
- **`pb/tools/serve.py`** is the preview dev server: it watches `registry.json` and renders through the
  *same* generator in memory, live-reloading the browser on every change (`/pb:preview`). It's the **one**
  preview per project — view it in any browser; `pb/tools/preview_register.py` keeps a single canonical
  `.claude/launch.json` entry when an in-app preview pane is used. Stdlib-only.
- **Memory:** `memory/constitution.md` (Principles + Stack/DS locks), `memory/decisions.md`,
  `design-system/{name}/`.

## Docs

- [prototype-builder.md](prototype-builder.md) — the playbook (registry contract, render inventory, governance).
- [CLAUDE.md](CLAUDE.md) — the router (the three loop rules + memory layout).
- [docs/architecture.md](docs/architecture.md) · [docs/data-flow.md](docs/data-flow.md) · [docs/CHANGES-from-v0.4.0.md](docs/CHANGES-from-v0.4.0.md)
- [changelog.md](changelog.md)

Design-system-agnostic: no hardcoded design system anywhere — set your tokens, components, and icon
source per project.
