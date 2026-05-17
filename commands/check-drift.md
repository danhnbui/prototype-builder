---
description: Manual drift audit across the trio (Tab 1, Tab 2, Tab 4-Component). Produces a report only — never writes to template.html. Run after marathon sessions to catch contradictions that slipped past per-prompt checks.
---

## User Input

```text
$ARGUMENTS
```

If user input names a specific principle (e.g., `principle #3`), scope the audit to that one. Otherwise, audit all principles against the entire trio.

## Execution flow

### Step 1 — Load inputs
- `.specify/memory/constitution.md` → Principles section
- `./prototype/template.html` → extract Tab 1, Tab 2, and Tab 4-Component content

If any input is missing → HARD FAIL with the missing-file message.

If Principles section is empty → output: `"No principles to check against."` End.

### Step 2 — Per-principle audit

For each numbered principle, examine each of Tab 1, Tab 2, Tab 4-C content. Ask:

> "Does this tab's content contradict principle N?"

Record each contradiction with: principle ID, tab affected, exact excerpt that contradicts, and a 1-line reason.

### Step 3 — Generate report

Output (do NOT write to template.html):

**If no contradictions**:

```
✅ Drift audit clean.

Principles checked: N
Tabs audited: Tab 1, Tab 2, Tab 4-Component
Contradictions: 0

The trio is in lockstep with constitution.md.
```

**If contradictions found**:

```
⚠ DRIFT REPORT — N contradictions found

Principle #1 — "<principle text>"
  ❌ Tab 1: <excerpt>
     because: <reason>
  ❌ Tab 4-C: <excerpt>
     because: <reason>

Principle #3 — "<principle text>"
  ❌ Tab 2 (UI Logic Trade-offs): <excerpt>
     because: <reason>

Suggested fixes:
  1. /speckit.prototype-builder.build  — re-derive Tab 1 + Tab 4-C from a corrected spec
  2. /speckit.clarify                   — revisit the trade-off in Tab 2
  3. /speckit.constitution              — amend the principle if it's the principle that's wrong
```

### Step 4 — Optional: write a report file

If user passes `--save` in `$ARGUMENTS`, write the report to:

```
.specify/memory/drift-reports/<YYYY-MM-DD-HHMMSS>.md
```

Otherwise, the report lives only in the chat output.

## Important rules

- **NEVER write to `./prototype/template.html`** from /check.drift. This is read-only audit.
- **NEVER auto-fix detected drift.** Always surface the suggested fixes; let the user decide.
- **NEVER silence a contradiction** because it seems minor. The point is to surface everything; user judges severity.
- **NEVER scope to fewer than all 3 trio tabs** unless user explicitly asks. The whole point is cross-trio inspection.
