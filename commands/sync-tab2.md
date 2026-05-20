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

### Step 3 — Update template.html *(executable recipe)*

Locate the `const PB_DATA = {` declaration in `./prototype/template.html` (grep for `const PB_DATA = {` — do not rely on a line number). It contains these top-level keys: `overview`, `userInsights`, `uiLogicTradeoffs`, `others`, `handoff`, `staleness`, `flow`, `erd`.

Use the **Edit tool** to replace **only** the value of each key you parsed in Step 2. Match the existing key + its current value as the `old_string`, swap in the new value as `new_string`. Touch nothing else.

Target shapes:

```js
// overview — replace the whole `overview: { … }` value
overview: {
  objectives: 'string from spec.md ## Objective, or null',
  principles: [ { num: 1, title: 'Name', body: 'description' }, … ],   // [] if none
},

// userInsights — replace the whole `userInsights: { … }` value
userInsights: {
  quantitative:     'string or null',
  researchSummary:  'string or null',
  executiveSummary: 'string or null',
},

// uiLogicTradeoffs — replace the whole `uiLogicTradeoffs: [ … ]` value
// NOTE: `title` is the topic only — the renderer prepends "Trade-off N — " itself.
// NOTE: `options` is an ARRAY of strings — the renderer maps it to <li> items.
uiLogicTradeoffs: [
  {
    title: 'Topic only, no "Trade-off N" prefix',
    question: '…',
    options: [ 'Option A', 'Option B' ],
    decision: '…', why: '…', tabsAffected: '…',
  },
  …
],   // [] if none
```

Escape every string for a JS single-or-double-quoted literal: backslash-escape the quote char you use, escape `\n` as needed, and never leave a raw `</script>` inside a string. If a source is malformed, skip that key (leave its existing value) and warn — never abort the whole sync.

### Step 3.5 — Verify the write

After editing:
1. Re-read the `const PB_DATA = {` block. Confirm it is still syntactically valid JS — balanced braces/brackets, every string closed, no stray commas.
2. If a browser preview is available, reload it and check the console for errors (a broken `PB_DATA` literal throws on load and blanks the whole prototype).
3. Switch to Tab 2 and confirm Overview / User Insights / UI Logic Trade-offs render the new content.

If verification fails, restore the previous value and report the parse error — do not leave a broken template.

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
