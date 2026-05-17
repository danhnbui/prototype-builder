---
description: Internal command. Re-renders Tab 2 of ./prototype/template.html from .specify/memory/constitution.md, the active spec.md, and the active clarify.md. Invoked automatically by the after_constitution / after_specify / after_clarify hooks. Safe to invoke manually if Tab 2 looks stale.
---

## User Input

```text
$ARGUMENTS
```

If `$ARGUMENTS` contains `--source=<constitution|specify|clarify>`, scope the update to just that source. Otherwise, refresh all 3 sources.

## Goal

Keep Tab 2 (Project Summary) in `./prototype/template.html` in lockstep with the upstream artifacts. This is the **auto-sync** mechanism for the trio's documentation layer.

## Execution flow

### Step 1 — Verify prereqs
- `./prototype/template.html` must exist. If missing → soft fail with: `"No template.html yet. Run /speckit.prototype-builder.scaffold first."`
- `.specify/memory/constitution.md` must exist for the principles update. Other sources are optional (empty-state copy is fine).

### Step 2 — Read sources

For each source not skipped by `--source=`:

**constitution.md → `PB_DATA.overview.principles`**
- Parse the `## Principles` section. Extract each `### N. Name` block.
- Build an array: `[{ num: N, title: 'Name', body: 'description' }, ...]`.

**spec.md → `PB_DATA.overview.objectives`**
- Find the active spec at `.specify/specs/[latest]/spec.md` (the most recent or the one matching the current git branch name).
- Parse the `## Objective` section. Extract its body text.
- Build a string for `PB_DATA.overview.objectives`.

**clarify.md → `PB_DATA.userInsights` + `PB_DATA.uiLogicTradeoffs`**
- Find the active clarify at `.specify/specs/[latest]/clarify.md`.
- Parse the `### Quantitative Data`, `### Research Summary Report`, `### Executive Summary` sub-headers under `## User Insights` → populate `PB_DATA.userInsights.{quantitative, researchSummary, executiveSummary}`.
- Parse the `### Trade-off N — ...` blocks under `## UI Logic Trade-offs` → populate `PB_DATA.uiLogicTradeoffs` as an array of `{ title, question, options, decision, why, tabsAffected }`.

### Step 3 — Update template.html

In `./prototype/template.html`, find the `const PB_DATA = { ... };` block (around line 530). Replace only the relevant nested keys (preserve `handoff`, `staleness`, and any other top-level keys you didn't touch).

Use a safe JSON-style serialization. Escape strings properly so the JS stays parseable.

### Step 4 — Confirm to user

```
✅ Tab 2 synced from <source(s)>.
   Principles: N
   Objective:  <set | empty>
   User Insights sub-sections: X populated, Y empty
   UI Logic Trade-offs: M
```

## Important rules

- **NEVER touch `PB_DATA.handoff`** — that's owned by /build and /handoff.
- **NEVER touch `PB_DATA.staleness`** — that's owned by the sync-flow / handoff / sync-erd commands.
- **NEVER fail the entire sync because one source is malformed.** Skip the bad source, sync the others, warn the user.
- **NEVER re-render the rest of template.html.** Only the `PB_DATA = { ... };` block changes.
