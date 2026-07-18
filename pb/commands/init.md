---
description: Scaffold a new Product Builder prototype — PRD intake (Q&A or file, never blank), set Stack + DS locks, seed registry.json + memory/. Optional --import <bundle> to ingest a context hand-off.
---

# /pb:init

Scaffold a new prototype. PRD intake is **never blank**. Where it scaffolds depends on the
context (see 0c): **greenfield** writes to the current directory; **adopt-in-place** (inside an
existing repo) sidecars everything under `.prototype/` and never touches the host code.

## 0 · Preflight — the one prerequisite
Verify **Python 3** is on PATH (it's the only runtime pb needs — the render/preview/check/update-version tools are
stdlib-only, no pip installs):
```
python3 --version
```
If that errors, STOP and print the OS-specific fix, then ask the user to install and re-run `/pb:init`:
- **macOS:** `xcode-select --install` (or install from python.org)
- **Windows:** install from python.org and tick "Add python.exe to PATH" (then use `py` / `python`)
- **Linux:** `sudo apt install python3` (Debian/Ubuntu) or your distro's package
Everything else pb uses ships with the plugin — there is nothing else to install.

## 0b · Flags
- `--import <bundle>` — ingest a context bundle from `/pb:handoff-close --context` instead of doing intake (step 6).
- `--figma <frame-url|id>` — start from a **Figma frame** instead of PRD intake — resolve its layers to DS components (step 6c). Sets `meta.entry = "figma"`.
- `--adopt` — force **adopt-in-place** mode (scaffold under `.prototype/`); see 0c.
- `--standalone` — force greenfield mode (scaffold at the current directory root), even inside an existing repo.

## 0c · Adopt-in-place vs greenfield (decide once — where pb scaffolds)
- **Greenfield** (default in an empty dir or an existing pb project): scaffold at the current
  directory root — `registry.json`, `memory/`, `design-system/`, `render/`, `prototype.html` all
  sit here. Steps 1–5 write to the root as usual.
- **Adopt-in-place** (default when `/pb:init` runs inside an existing git repo that already has a
  host codebase): pb must **not** pollute someone else's repo. Detect it, then sidecar:

  1. **Detect** — `git rev-parse --is-inside-work-tree` is true **and** `git ls-files` shows tracked
     files that aren't a pb project. Override either way with `--adopt` / `--standalone`.
  2. **Sidecar under `.prototype/`** — create a `.prototype/` directory; it is the pb **project
     root**. Steps 1–5 scaffold **inside `.prototype/`** (`.prototype/registry.json`,
     `.prototype/memory/`, `.prototype/render/`, …). Every later `/pb:*` command operates with
     `.prototype/` as its working directory.
  3. **Gitignore** — append the pb block to the host `.gitignore` (create it if absent), idempotent
     and never duplicated (skip if the block is already present):
     ```
     # Product Builder (pb) — prototype sidecar under .prototype/
     # Derived + transient artifacts; the registry/render/memory sources stay trackable.
     # To ignore the whole sidecar instead, replace the lines below with:  .prototype/
     .prototype/prototype.html
     .prototype/history/
     .prototype/.preview/
     ```
  4. **Read-only-outside rule** — append this Principle to `.prototype/memory/constitution.md`
     (after the seeded Principles):
     > **Adopt-in-place (read-only outside).** This prototype lives entirely under `.prototype/`.
     > pb treats everything outside `.prototype/` as **read-only** — it never creates, edits, or
     > deletes host-repo files. The one exception is the pb block appended to the host `.gitignore`
     > at `/pb:init`. Every `/pb:*` command runs with `.prototype/` as the project root.

  In this mode, **never** write pb artifacts outside `.prototype/` (besides that one `.gitignore`
  append). When a path below says `registry.json` / `memory/` / etc., read it as
  `.prototype/registry.json` / `.prototype/memory/`.

## 1 · PRD intake (never blank)
Never start empty. Source it one of two ways:
- **File** — a path in `$ARGUMENTS` or a `docs/prd/*.md`: read it; invoke `ref-prd` to parse and
  `think-critique-prd` to surface gaps.
- **Q&A** — otherwise ask, one at a time: (1) the product/feature in a line; (2) who it's for;
  (3) the core problem; (4) the 3–6 key screens; (5) what success looks like. Use `think-clarify` to
  decide what genuinely needs asking vs a sensible default.

Write a short PRD (objective + key screens + success criteria) to `memory/prd.md`.

## 2 · Set the locks (confirm with the user)
- **Stack Lock** — language + framework (e.g. TypeScript + React).
- **Design System Lock** — name + **platform** (`web` / `ios` / `android` / `desktop`) + the
  **clone source**, asked as the fallback ladder (stop at the first the user has):
  1. a **dedicated DS MCP** (a design-system export tool), 2. a **Figma design-system link**,
  3. the **current code library** (repo/path with tokens), 4. a **common DS** (`built-in` / `mui`).
  Record the chosen `{ type, ref }` — it becomes `meta.dsSource` when the DS is cloned (2b).

Write `memory/constitution.md` from `${CLAUDE_PLUGIN_ROOT}/template/constitution.template.md`, filling
Stack Lock + DS Lock + a first cut of Principles (from the PRD + DS rules). Keep it lean.

## 2b · Clone the design system (offer — via `/pb:pull-ds`)
Offer to clone the DS now from the source captured in the DS Lock:
```
/pb:pull-ds <source>
```
It resolves the ladder, seeds `registry.json` tokens, writes `design-system/<name>/<name>.md` +
`.source.json`, and records `meta.dsSource` + confirms `meta.platform`. Skippable — the project
still scaffolds with an empty DS reference (step 4) and the user can run `/pb:pull-ds` later. If they
skip, leave `meta.dsSource: null` and set `meta.platform` from the DS Lock answer.

## 3 · Seed the registry
Copy `${CLAUDE_PLUGIN_ROOT}/template/registry.template.json` → `registry.json`; set `meta.name`.
The template already carries `meta.schemaVersion: 4` (= `CURRENT_SCHEMA` from
`pb/migrations/manifest.py`) and a pre-seeded `danger` token (the validation runtime needs it).
Leave `components` / `screens` empty — `/pb:build` fills them and creates their
`render/{components,screens}/<id>.js` body files.

**Ask the user up front what platform + devices this project covers** (one Q&A, even in file
intake): *"Is this a browser app or a native/installed application, and which screen sizes does it
target?"* Use the answer to seed:

- **`meta.shell`** (`'browser' | 'app'`) — the default Prototype chrome. `'browser'` adds a tab strip
  + back/reload/URL bar; `'app'` shows a plain titlebar (a device status bar — clock + signal/wifi/battery, auto black/white for contrast — on tablet/mobile). Web apps,
  dashboards, marketing sites → `'browser'`; native/installed/mobile apps → `'app'`. The viewer can
  flip this live, but the lock sets the default. Default `'browser'` when unclear.
- **`meta.device`** (`'monitor' | 'laptop' | 'tablet' | 'mobile'`) — the default device frame, from
  the PRD's primary form factor: mobile-first apps → `'mobile'`; dashboards/desktop web → `'laptop'`;
  big-screen/data-dense → `'monitor'`; when unclear, default `'laptop'`.
- **`meta.devices`** — the fixed sizes this project supports (any subset of the four:
  `monitor 1920×1080 · laptop 1280×832 · tablet 834×1112 · mobile 390×844`). Sizes **not** listed are
  disabled in the Prototype switcher. Default all four. *(Legacy `'desktop'` is still honored — the
  shell expands it to `monitor` + `laptop`.)*

Seed **`meta.designSystem`** from the Design System Lock (step 2): `name` = the DS name; `codeLibrary` =
its source when that's a repo URL or local path (**required** — a DS must have a code home); `designLink` =
a Figma/doc URL if one was given (else `null`); `linked: true` once both name and codeLibrary are set.
This drives the UI Design design-system bar.

Also set **`meta.platform`** from the DS Lock (step 2) — `web` / `ios` / `android` / `desktop`
(default `web`). Leave **`meta.dsSource: null`** unless the DS was cloned in 2b (then `/pb:pull-ds`
already set it). Both fields are seeded in the template at `meta.schemaVersion 5`.

## 4 · Seed memory + design system
- `memory/decisions.md` from `${CLAUDE_PLUGIN_ROOT}/template/decisions.template.md`.
- `design-system/{name}/{name}.md` — a starting DS reference (foundations + an empty component index +
  rules R0–R4 + the naming contract). The full template lands in Phase 5.

## 5 · Fold the Tab-2 sync (no hook)
Write into `registry.json`: `meta.overview.objectives` = the PRD objective; `meta.overview.principles`
= the constitution Principles as `[{num,title,body}]`. This is the Project-Summary sync the v0.4.0
`after_*` hooks used to do — it now lives here. **Do not render yet.**

## 5b · Install the pb agents (optional — enables `/pb:orchestrate`)
After scaffolding, offer to install the 8 `pb-*` agents into this project's `.claude/agents/` so
`/pb:orchestrate` can dispatch tasks to them:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/agents_install.py" --project-dir .
```
It copies the roster (`pb-clarifier` · `pb-planner` · `pb-builder` · `pb-design-system` · `pb-flow` ·
`pb-data` · `pb-tester` · `pb-reviewer`) into `.claude/agents/`, idempotently (safe to re-run). Skip it for
a plain single-slice `/pb:build` workflow — it's only needed for the agent-wave orchestration path. Mention
to the user that they can run it later if they decide to use `/pb:orchestrate`.

## 6 · `--import <bundle>` (alternative on-ramp)
If set, skip 1–5: read the bundle (`registry.json` + `render/` body files + `design-system/` +
`memory/constitution.md` + `memory/decisions.md`), copy it **all** into the new project (the
`render/` tree is required — without it the registry's `renderSrc` references dangle), confirm the locks.

**Schema compatibility check** (see **Schema compatibility** in `CLAUDE.md`) — run it here, on the
imported `registry.json`, before proceeding. If the bundle is on an older schema, show the banner and
suggest `/pb:update-version`. Do not silently copy an out-of-contract slice into the project. Ready to `/pb:build`.

## 6c · `--figma <frame>` (the second entry door)
If set, start from a Figma frame instead of PRD intake (steps 1–5 still seed the locks + registry;
`meta.entry = "figma"`). This door holds **DS fidelity at entry** — it maps to components that already
exist, and never invents one.

1. **Need a DS first.** The frame's layers map to the project's design system, so a DS must be cloned
   (`meta.dsSource` set). If none is, run `/pb:pull-ds` (step 2b) before resolving.
2. **Read + normalize the frame.** Invoke the **`ref-figma-frame`** skill: read the frame via the Figma
   MCP and normalize it to a **frame-export** (`{ frame:{id,name}, layers:[{name,type,component?}] }`),
   resolving each Figma component instance to its DS component id where possible. Write it to a temp file.
3. **Resolve (deterministic).**
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/resolve_frame.py" --from .pb-frame.json registry.json
   ```
   It emits a **screen patch** (elements → `orgId` for mapped layers), logs every unmapped layer to
   **`gaps.md`** as a labeled placeholder (never invented), and sets `meta.entry = "figma"`. Delete the
   temp file after. Surface the tool's summary + the gaps to the user.
4. **Next:** `/pb:build` to flesh out the screen's render body from the resolved elements; resolve each
   `gaps.md` entry by cloning/adding the missing component then re-resolving, or building it.

## Result
A seeded project — non-empty `memory/prd.md`, locks set, `registry.json` seeded, `memory/decisions.md`,
`design-system/{name}/` (all under `.prototype/` in adopt-in-place mode, plus the host `.gitignore`
block + the read-only-outside Principle). Next: `/pb:specify` (expand) or `/pb:build` (start building).

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
