# Product Builder v1.8.0

A standalone, CLAUDE.md-native prototype builder for Claude Code. Turn a PRD into an interactive,
self-documenting **5-tab prototype** — a real click-through flow you preview at desktop / tablet /
mobile — with a cheap build loop, a small memory layer, and a
**design-system-agnostic** core. State lives in a compact `registry.json`; `prototype.html` is a
rendered view, regenerated deterministically (so the build loop edits tens of lines of JSON, not a
3,600-line file).

Every tab shares **one unified, two-column layout** (v1.4): a header with a `?` info dialog (what the tab
does, its commands and skills) over a main canvas + a context aside. Highlights — a device-framed Prototype
with a component structure tree; a UI Design tab that groups components by atomic level, links your design
system, and previews Figma-push reuse + affected screens; QA-authored UX test cases with coverage-gap
warnings; and an ERD mock-data viewer for checking empty / sparse / overflow edge cases.

**New in v1.5** — an agent-powered testing **sandbox** (`/pb:test`: run authored scenarios, preview as
role-gated users, plus server-reachability and secrets/PII checks), a **multi-agent orchestrator**
(`/pb:orchestrate` dispatches the per-tab task plan to 8 specialized agents in dependency waves;
`/pb:explore` proposes parallel design options), and an ⌥-hover **element inspector** that copies a precise
`screen › element › component` reference to feed the AI. All additive — a pre-v1.5 project behaves unchanged.

## Install (it's a Claude Code plugin)

**From GitHub (recommended):**

```
/plugin marketplace add danhnbui/prototype-builder
/plugin install pb@product-builder
```

**Local development (if you have the repo cloned):**

```
/plugin marketplace add ./
/plugin install pb@product-builder
```

Restart Claude Code — the commands appear as `/pb:*`. (User-scope; the commands are global, per-project
state stays in each prototype's folder.)

**Full capability with zero external skills** — every skill the commands use ships inside the plugin
(`pb/skills/`), so a fresh install works for anyone with no personal/employer skill set required. The
**only** thing pb needs on your machine is **Python 3** (already present on most Macs and Linux; on Windows
install it from python.org and tick "Add to PATH"). No other setup, no `pip install`.

## Non-technical quickstart (for PMs & designers)

No terminal knowledge needed — you just talk to Claude Code:

1. **Install** — paste the two `/plugin` lines above into Claude Code, then **restart** it.
2. **Start a project** — type `/pb:init` and answer a few questions about your product (or point it at a
   PRD file). It sets things up for you.
3. **See it live** — type `/pb:preview`. A prototype opens in your browser and updates by itself as you build.
4. **Build by asking** — type `/pb:build` and describe the screen or change you want, in plain language.
5. **Share it** — type `/pb:handoff-close --people` to get a single self-explaining file you can send to anyone.

If `/pb:init` says Python isn't installed, it will tell you exactly how to fix it for your computer.

## Commands

| Command | Does |
|---|---|
| `/pb:init` | Scaffold: PRD intake (Q&A or file), set Stack + DS locks, seed `registry.json` + `memory/`; `--import` a bundle |
| `/pb:specify` | Produce the spec / PRD |
| `/pb:clarify` | User Insights + UI Logic Trade-offs → Project Summary; append to `decisions.md` |
| `/pb:plan` | Implementation plan + per-tab task breakdown (acceptance + skill + **agent · deps · slice**) |
| `/pb:orchestrate` | Dispatch `memory/tasks.md` to the 8-agent roster in dependency **waves** — serial writes, render once per wave, acceptance-gated |
| `/pb:build` | The cheap loop: targeted `registry.json` patches, trio-gated, no per-tweak render; `--render` to view |
| `/pb:pull-ds` | Clone the design system (DS MCP → Figma link → code library → common) → registry tokens + a scannable reference + a `.source.json` drift snapshot; records `meta.dsSource` + `meta.platform` |
| `/pb:preview` | Live preview dev server: watch `registry.json` → render → live-reload the browser (start once, leave running) |
| `/pb:preview-ds` | Storybook-style server for the cloned DS: token foundations as swatches + the component catalog (read-only) |
| `/pb:test` | Sandbox testing: scenario `test{}` blocks (functional), `--roles`, `--server`, `--security`, `--explore` → live ✓/✗ glyphs |
| `/pb:explore` | Parallel design options: N `pb-builder` agents propose alternatives → compare → keep one |
| `/pb:build-check-design-system` | DS-first reuse → variant → local + naming contract |
| `/pb:build-figma-handoff` | One-way registry → Figma (6 gates incl. G-FP6 render audit, DS-neutral, auto-layout) |
| `/pb:flow` | UX Design / Flow — wireflow + test checklist (decoupled) |
| `/pb:data` | Data — field/type/example table + ERD (decoupled) |
| `/pb:check-drift` | Read-only drift audit of the trio vs the constitution |
| `/pb:handoff-close` | Close out into one `handoff/` folder: view-only `prototype.html` + portable `bundle/` + a recipient `AGENTS.md` (`--people` / `--context` narrow it) |
| `/pb:validate` | Wrap `prototype.html` in a runnable reference build (Vite/Next) — serves the single file, not a component export |
| `/pb:handoff-dev` | Export at a tier — `--tier=host` (runnable prototype) · `scaffold` (deterministic React+Tailwind app) · `hardened` (idiomatic/DS-integrated — deferred) |
| `/pb:update-version` | Schema version update: dry-run / `--apply` / `--rollback` / `--to <N>` |
| `/pb:snapshot` | Timestamped `registry.json` history under `<project>/history/` (`--list` / `--restore`); never branches |

## Quickstart

1. `/pb:init` — intake a PRD, set the locks, seed the project. (Or `--figma <frame>` to start from a Figma frame — layers resolve to DS components, unmapped ones logged to `gaps.md`.)
2. `/pb:specify` → `/pb:clarify` → `/pb:plan` — shape the spec, insights, and tasks.
3. `/pb:preview` (start once, leave running) → `/pb:build` — the preview server live-reloads on every
   registry change; no `--render` needed during the build loop.
4. `/pb:flow` / `/pb:data` — populate the UX Design and Data tabs (on demand).
5. `/pb:handoff-close --people` — a view-only artifact to share; `--context` to hand to another builder.
6. `/pb:validate` — wrap the single-file prototype in a runnable reference build (Vite/Next) to host it.
   (It serves `prototype.html`; it does not export reusable component code — see the Engineering note below.)

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
- [docs/architecture.md](docs/architecture.md) · [docs/data-flow.md](docs/data-flow.md) · [docs/upgrading.md](docs/upgrading.md)
- [changelog.md](changelog.md)

Design-system-agnostic: no hardcoded design system anywhere — set your tokens, components, and icon
source per project.
