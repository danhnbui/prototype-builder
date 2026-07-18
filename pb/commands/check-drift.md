---
description: Read-only drift audit of the trio (screens, components, logic) against memory/constitution.md. Produces a report only — never writes to registry.json or prototype.html. Run after long sessions to catch contradictions that slipped past per-prompt checks.
---

# /pb:check-drift

Manual, **read-only** drift audit across the **trio** (screens · components · logic) against the
constitution. Produces a report only — it **never** writes to `registry.json` or `prototype.html`.

## 1 · Load inputs
- `memory/constitution.md` → `## Principles`.
- `registry.json` → the trio: `screens[]`, `components[]`, and the logic in `elements[].uiLogic` /
  `components[].uiLogic` / `screens[].logicNotes`. When a component/screen has a `renderSrc`, read its
  body file (`render/components/<id>.js` / `render/screens/<id>.js`) too — that is where the actual
  markup/logic lives in v1.4.

If an input is missing → HARD FAIL with the missing-file message. If Principles is empty →
`"No principles to check against."` and end. (`$ARGUMENTS` may name one principle, e.g. `principle #3`,
to scope the audit.)

## 2 · Per-principle audit
For each numbered principle, examine every screen, component, and logic note. Ask: *"Does this
contradict principle N?"* Record each hit: principle id · where (screen/component id) · the exact
excerpt · a one-line reason.

## 3 · Report (no writes)
- **Clean:** `✅ Drift audit clean. Principles checked: N · Contradictions: 0 — the trio is in lockstep with the constitution.`
- **Contradictions:** a `⚠ DRIFT REPORT — N found` block, grouped by principle, each with the offending
  excerpt + reason, then **Suggested fixes** referencing `/pb:build` (re-derive the slice),
  `/pb:clarify` (revisit a trade-off), or editing `memory/constitution.md` (if the principle is wrong).

If `--save` is in `$ARGUMENTS`, also write the report to `memory/drift-reports/<YYYY-MM-DD-HHMMSS>.md`.

## 4 · Shell coherence (advisory · read-only)

A separate, advisory check that does **not** touch the trio and **never** blocks. It catches the case
that motivated it: `prototype.html` left rendered by an **older plugin shell** than the one now installed
(the silent stale render).

- Read `prototype.html` next to `registry.json`. Near the top, find the stamp comment
  `<!-- pb-shell vX.Y.Z · rendered <ISO-8601> -->` and parse the version with `<!-- pb-shell v(\S+) ·`.
- Read the installed plugin version from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` (`version`).
  Outside a plugin checkout, fall back to `pb/.claude-plugin/plugin.json`.
- Compare and report exactly one line:
  - **Match** → `✅ Shell coherent — prototype.html rendered by pb vX.Y.Z (current).`
  - **Mismatch** → `⚠ Shell drift: prototype.html rendered by pb vX.Y.Z; current plugin is vA.B.C — re-render (/pb:build --render) or restart /pb:preview.`
  - **No stamp** (an artifact rendered by a plugin older than this feature) → `⚠ Shell unstamped: prototype.html has no pb-shell stamp — re-render with the current plugin to enable drift detection.`
  - **No `prototype.html`** → skip silently (nothing rendered yet).

Report this alongside the trio drift report. It is **advisory**: never edit `prototype.html`, never block.

## 5 · DS drift — clone vs source (advisory · read-only)

Another advisory check (does **not** touch the trio, **never** blocks): has the cloned design system
drifted from its live source since `/pb:pull-ds` ran?

- Skip silently if `meta.dsSource` is `null` or `design-system/<name>/.source.json` is missing
  (nothing cloned yet).
- Otherwise **re-resolve the current source** — the same fallback ladder `/pb:pull-ds` uses
  (`meta.dsSource.type` + `.ref`: a DS MCP, a Figma link, a code library, or a common preset) —
  and normalize it to a fresh DS-export (invoke `ref-design-system`). Write it to a temp file.
- Compare it against the stored snapshot:
  ```
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/clone_ds.py" --drift <fresh-export.json> registry.json
  ```
  Exit `0` = in sync; exit `3` = drift (the tool prints each changed/added/removed token + component).
  Delete the temp file after.
- Report exactly one block:
  - **In sync** → `✅ DS coherent — <name> clone matches source.`
  - **Drift** → the tool's `⚠ DS DRIFT …` list, then: *re-run `/pb:pull-ds` to re-clone, or reconcile
    intentionally.* Advisory — never auto re-clone, never block.
- If the source can't be re-resolved (MCP/link unavailable), say so and skip — don't guess.

## NEVER
- NEVER write to `registry.json` / `prototype.html` — this is a read-only audit.
- NEVER auto-fix drift — surface the fixes; the user decides.
- NEVER silence a contradiction because it seems minor — surface everything; the user judges severity.
- NEVER scope to fewer than all 3 trio surfaces unless the user explicitly asks.
