---
description: Scaffold a new Product Builder prototype — PRD intake (Q&A or file, never blank), set Stack + DS locks, seed registry.json + memory/. Optional --import <bundle> to ingest a context hand-off.
---

# /pb:init

Scaffold a new prototype **in the current directory**. PRD intake is **never blank**.

## 0 · Preflight — the one prerequisite
Verify **Python 3** is on PATH (it's the only runtime pb needs — the render/preview/check/migrate tools are
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
- `--import <bundle>` — ingest a context bundle from `/pb:hand-off --context` instead of doing intake (step 6).

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
- **Design System Lock** — name + source (git URL / local path / built-in).

Write `memory/constitution.md` from `${CLAUDE_PLUGIN_ROOT}/template/constitution.template.md`, filling
Stack Lock + DS Lock + a first cut of Principles (from the PRD + DS rules). Keep it lean.

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

## 4 · Seed memory + design system
- `memory/decisions.md` from `${CLAUDE_PLUGIN_ROOT}/template/decisions.template.md`.
- `design-system/{name}/{name}.md` — a starting DS reference (foundations + an empty component index +
  rules R0–R4 + the naming contract). The full template lands in Phase 5.

## 5 · Fold the Tab-2 sync (no hook)
Write into `registry.json`: `meta.overview.objectives` = the PRD objective; `meta.overview.principles`
= the constitution Principles as `[{num,title,body}]`. This is the Project-Summary sync the v0.4.0
`after_*` hooks used to do — it now lives here. **Do not render yet.**

## 6 · `--import <bundle>` (alternative on-ramp)
If set, skip 1–5: read the bundle (`registry.json` + `render/` body files + `design-system/` +
`memory/constitution.md` + `memory/decisions.md`), copy it **all** into the new project (the
`render/` tree is required — without it the registry's `renderSrc` references dangle), confirm the locks.

**Schema compatibility check** (see **Schema compatibility** in `CLAUDE.md`) — run it here, on the
imported `registry.json`, before proceeding. If the bundle is on an older schema, show the banner and
suggest `/pb:migrate`. Do not silently copy an out-of-contract slice into the project. Ready to `/pb:build`.

## Result
A seeded project — non-empty `memory/prd.md`, locks set, `registry.json` seeded, `memory/decisions.md`,
`design-system/{name}/`. Next: `/pb:specify` (expand) or `/pb:build` (start building).

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
