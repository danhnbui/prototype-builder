---
description: Hand off the prototype in one of two modes. --people produces a view-only, self-documenting prototype.html with an auto-generated cover (authoring CTAs hidden). --context exports a portable bundle (registry.json + design-system.md + constitution.md + decisions.md) that /pb-init --import can ingest.
---

# /pb:hand-off

Hand the prototype off in one of two modes.

## 0 · Contract gate (fail-closed — runs first, both modes)
Before rendering or bundling anything, run the contract validator in **strict** mode:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/check.py" --strict registry.json
```
If it exits non-zero (any `ERROR`), **STOP** — do not render, do not export. Print the
findings and tell the user to fix them (or run `/pb:build` to patch) and retry. This
mirrors G-FP6's role for the Figma push: a hand-off must never ship a registry that
violates the contract (NS6, fail-closed). Only on a clean exit (0) proceed below.

## `--people` — a view-only, self-documenting artifact
1. `/pb:build --render` first.
2. Set `registry.json` → `config.viewOnly = true` and `config.cover = { title, summary, date, by }`
   (auto-generated from `meta.name` + `meta.overview.objectives`); then `--render` again.
3. On `config.viewOnly` the shell **hides every authoring CTA** (Push-to-Figma buttons, build controls)
   and shows the cover. The output opens in any browser, explains itself, and is read-only.

Output: one `prototype.html` (or `--out <file>`) safe to share with non-builders.

## `--context` — a portable bundle for another builder
Export a bundle (`handoff-bundle/` or `--out <dir>`) containing:
- `registry.json` · `design-system/` · `memory/constitution.md` · `memory/decisions.md`

The exported `registry.json` carries `meta.schemaVersion` — the bundle is schema-stamped so
`/pb:init --import` can detect and suggest `/pb:migrate` if the receiving environment is newer.

This is exactly what `/pb:init --import <bundle>` ingests to continue the work in a fresh project.

## NEVER
- NEVER ship a `--people` file with authoring CTAs visible — must set `config.viewOnly`.
- NEVER hand off a stale render — `--render` first in both modes.
- NEVER omit `constitution.md` / `decisions.md` from `--context` (they carry the why + the locks).
