# Product Builder v2.0.0

A standalone, CLAUDE.md-native prototype builder for Claude Code. Turn a PRD into two interactive,
self-documenting sites from **one `registry.json`** — a **4-tab prototype** (a real click-through flow
you preview at desktop / tablet / mobile) and a live **design-system site** (every component as an
interactive demo + variant grid + Push-to-Figma snippet) — with a cheap build loop, a small memory
layer, and a **design-system-agnostic** core. State lives in a compact `registry.json`; both
`prototype.html` and `design-system.html` are rendered views, regenerated deterministically (so the
build loop edits tens of lines of JSON, not a 3,600-line file).

Every tab shares **one unified, two-column layout** (v1.4): a header with a `?` info dialog (what the tab
does, its commands and skills) over a main canvas + a context aside. Highlights — a device-framed Prototype
with a component structure tree; a standalone **design-system site** (served at `/design-system`) that
auto-collects every registry component into a live interactive demo + variant grid + Push-to-Figma bridge
snippet over the token foundations; QA-authored UX test cases with coverage-gap warnings; and an ERD
mock-data viewer for checking empty / sparse / overflow edge cases.

**New in v2.0 — twenty-four commands are now twelve.** Every merged command's old name is
**gone, not aliased**, which is what makes this a major: `/pb:flow` is `/pb:plan --flow`,
`/pb:check-drift` is `/pb:test --drift`, `/pb:validate` is `/pb:handoff --tier=host`, and the four
hand-off commands are one `/pb:handoff` that asks who is receiving the work. Upgrading an existing
project takes about five minutes — **[docs/upgrade-to-2.0.md](docs/upgrade-to-2.0.md)** has the full
rename table and the one command that moves your registry.

Also in 2.0: **`/pb:test` plans the run, then delegates the grading** — it writes a yes/no test plan
and hands it to subagents that never saw the design being built, so a verdict is not written by the
context that authored the thing under test. A **trade-off is stored as a rule** carrying the decision
it was made by, so it lives beside the other rules in UX Design → Logic. **UX Design is five
segments** — Logic, Information Architecture, User Flow, Test Cases, and a new **Content** segment
holding a glossary over the canonical wording for every action, status and message. And `/pb:build`
**keeps the flow and data slices in sync** after any structural patch — no Sync button, no second
command.

**Earlier** — one registry projected into two sites, both rendered by Python at ~0 model tokens
(v1.11); an agent-powered testing sandbox and a multi-agent orchestrator (v1.5); the unified
two-column tab layout and the ⌥-hover element inspector (v1.4–v1.9).


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
5. **Share it** — type `/pb:handoff --people` to get a single self-explaining file you can send to anyone.

If `/pb:init` says Python isn't installed, it will tell you exactly how to fix it for your computer.

## Commands

Twelve commands. Flags narrow a command; they are not commands of their own.

| Command | Does |
|---|---|
| `/pb:init` | Scaffold: PRD intake (Q&A or file), set Stack + DS locks, seed `registry.json` + `memory/`. `--import <bundle>` to adopt one; `--figma <frame>` to start from a Figma frame |
| `/pb:pull-ds` | Clone the design system (DS MCP → Figma link → code library → common) → registry tokens + a scannable reference + a `.source.json` drift snapshot |
| `/pb:specify` | Produce the spec / PRD |
| `/pb:clarify` | User Insights → Project Summary; each contested UI decision becomes one `ia.rules[]` rule carrying the decision it was made by; appends to `decisions.md` |
| `/pb:plan` | Implementation plan + per-tab task breakdown (acceptance · skill · agent · deps · slice), and the first authoring of the flow and data slices (`--flow` / `--data` / `--mock`) |
| `/pb:orchestrate` | Dispatch `memory/tasks.md` to the 8-agent roster in dependency **waves** — serial registry writes, render once per wave, acceptance-gated |
| `/pb:build` | The cheap loop: targeted `registry.json` patches, trio-gated, no per-tweak render. Runs the DS-first reuse → variant → local check on every new component, and keeps flow + data in sync. `--render` to regenerate both sites |
| `/pb:preview` | Live preview dev server: watch `registry.json` → render → live-reload. One server, two routes — the prototype at `/`, the design-system workbench at `/design-system` |
| `/pb:test` | **Check everything.** No flag = scenarios · roles · server · security · drift · health · shell coherence · DS drift, one verdict. Writes a yes/no test plan, then delegates it to subagents that never saw the design. A flag narrows it (`--drift`, `--roles`, `--security`, …) |
| `/pb:explore` | An **id** → N agents diverge that render body, scored against a rubric, keep one. A **goal sentence** → the gated discovery pipeline |
| `/pb:handoff` | The one hand-off. Asks who is receiving it: **1** everything incl. a vendored Product Builder · **2** engineering (`--tier=host` runnable · `--tier=scaffold` React+Tailwind) · **3** Figma |
| `/pb:update-version` | Schema version update: dry-run / `--apply` / `--rollback` / `--to <N>` |

## Quickstart

1. `/pb:init` — intake a PRD, set the locks, seed the project. (Or `--figma <frame>` to start from a Figma frame — layers resolve to DS components, unmapped ones logged to `gaps.md`.)
2. `/pb:specify` → `/pb:clarify` → `/pb:plan` — shape the spec, insights, and tasks.
3. `/pb:preview` (start once, leave running) → `/pb:build` — the preview server live-reloads on every
   registry change; no `--render` needed during the build loop.
4. `/pb:test` — scenarios, roles, security and drift in one verdict, graded by agents that did not build it.
5. `/pb:handoff` — it asks who is receiving the work: a viewer, engineering, or Figma.

`/pb:plan --flow` and `--data` author the UX Design and Data slices **once**; from then on
`/pb:build` reconciles them itself. **Upgrading a 1.x project?** → [docs/upgrade-to-2.0.md](docs/upgrade-to-2.0.md).

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
- [DESIGN.md](DESIGN.md) — the standing rationale: what pb is deliberately bad at, and why.
- [docs/upgrade-to-2.0.md](docs/upgrade-to-2.0.md) — **upgrading a 1.x project** (start here if you have one).
- [docs/architecture.md](docs/architecture.md) · [docs/data-flow.md](docs/data-flow.md) · [docs/upgrading.md](docs/upgrading.md)
- [changelog.md](changelog.md)

Design-system-agnostic: no hardcoded design system anywhere — set your tokens, components, and icon
source per project.
