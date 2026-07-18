---
description: Close out the prototype into a single self-contained handoff/ folder — a view-only prototype.html, a portable bundle/ (ingestible by /pb:init --import), and a generated AGENTS.md that orients whoever receives it. --people / --context narrow to one piece.
---

# /pb:handoff-close

Close out the prototype into **one deliverable folder, `handoff/`** (or `--out <dir>`):

```
handoff/
  prototype.html      # view-only, self-documenting — open in any browser
  AGENTS.md           # orients the recipient (person or a fresh agent session)
  bundle/             # portable source of truth — /pb:init --import handoff/bundle
    registry.json
    render/           # the render body files (renderSrc targets — required)
    design-system/
    memory/constitution.md
    memory/decisions.md
```

Default (no flag) writes **all three**. `--people` writes only the view-only prototype;
`--context` writes only the bundle. Both narrowed modes still emit `AGENTS.md`.

## 0 · Contract gate (fail-closed — runs first, every mode)
Before rendering or bundling anything, run the contract validator in **strict** mode:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/lint_registry.py" --strict registry.json
```
If it exits non-zero (any `ERROR`), **STOP** — do not render, do not export. Print the
findings and tell the user to fix them (or run `/pb:build` to patch) and retry. A hand-off
must never ship a registry that violates the contract (NS6, fail-closed). Only on a clean
exit (0) proceed.

## 1 · The view-only prototype (default + `--people`)
1. `/pb:build --render` first (never hand off a stale render).
2. Set `registry.json` → `config.viewOnly = true` and `config.cover = { title, summary, date, by }`
   (auto-generated from `meta.name` + `meta.overview.objectives`); then `--render` again.
3. On `config.viewOnly` the shell **hides every authoring CTA** (Push-to-Figma buttons, build
   controls, sync bars, empty-state actions) and shows the cover. Role switcher + Reset stay
   visible to viewers. The output opens in any browser, explains itself, and is read-only.
4. Write it to `handoff/prototype.html`.

## 2 · The portable bundle (default + `--context`)
Copy into `handoff/bundle/`, preserving the shape `/pb:init --import` expects:
- `registry.json` — carries `meta.schemaVersion` (schema-stamped, so `--import` can detect an
  older schema and suggest `/pb:update-version`)
- `render/` — the body files (**required**, or `renderSrc` references dangle)
- `design-system/`
- `memory/constitution.md` · `memory/decisions.md` (the why + the locks)

`/pb:init --import handoff/bundle` ingests this to continue the work in a fresh project.

## 3 · The recipient AGENTS.md (every mode)
Render `${CLAUDE_PLUGIN_ROOT}/template/AGENTS.template.md` to `handoff/AGENTS.md`, filling:
- `{{PROJECT_NAME}}` ← `meta.name`
- `{{SUMMARY}}` ← first line of `meta.overview.objectives`
- `{{DATE}}` ← today (from the shell, `date +%Y-%m-%d`)
- `{{SCHEMA_VERSION}}` ← `meta.schemaVersion`
- `{{MODE}}` ← `full` / `people` / `context` (what this hand-off contains)

It tells whoever opens `handoff/` what the folder is, that `prototype.html` is a derived
view-only snapshot (never hand-edit it), and how to continue building from `bundle/`.

## NEVER
- NEVER ship a view-only `prototype.html` with authoring CTAs visible — must set `config.viewOnly`.
- NEVER hand off a stale render — `--render` first.
- NEVER omit `constitution.md` / `decisions.md` from the bundle (they carry the why + the locks).
- NEVER hand-edit anything under `handoff/` — regenerate by re-running `/pb:handoff-close`.

> **Skill degrade (NS6).** If a step's tool or template fails to load, say so explicitly and
> proceed with its core intent — never silently skip it.
