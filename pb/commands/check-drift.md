---
description: Read-only drift audit of the trio (screens, components, logic) against memory/constitution.md. Produces a report only — never writes to registry.json or prototype.html. Run after long sessions to catch contradictions that slipped past per-prompt checks.
---

# /pb:check-drift

Manual, **read-only** drift audit across the **trio** (screens · components · logic) against the
constitution. Produces a report only — it **never** writes to `registry.json` or `prototype.html`.

## 1 · Load inputs
- `memory/constitution.md` → `## Principles`.
- `registry.json` → the trio: `screens[]`, `components[]`, and the logic in `elements[].uiLogic` /
  `components[].uiLogic` / `screens[].logicNotes`.

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

## NEVER
- NEVER write to `registry.json` / `prototype.html` — this is a read-only audit.
- NEVER auto-fix drift — surface the fixes; the user decides.
- NEVER silence a contradiction because it seems minor — surface everything; the user judges severity.
- NEVER scope to fewer than all 3 trio surfaces unless the user explicitly asks.
