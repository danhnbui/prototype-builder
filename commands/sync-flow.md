---
description: Generate or update Tab 3 (User Flow). Produces a Mermaid `flowchart` diagram following the 18 enforced rules of the user-flow guide + a numbered list of user stories that act as the test checklist. Tab 3 is decoupled — never auto-triggers.
---

## User Input

```text
$ARGUMENTS
```

If user input names a specific story or flow, scope to that. Otherwise, generate the full flow across all P1/P2/P3 user stories in spec.md.

## Execution flow

### Step 1 — Read inputs
- `.specify/specs/[active]/spec.md` → user stories, JTBDs, acceptance scenarios
- `.specify/specs/[active]/plan.md` → per-story approach, state transitions

### Step 2 — Read the user-flow guide (required)
The full set of 18 enforced rules + shape standard + validation checklist lives in [`docs/USER-FLOW-GUIDE.md`](../../docs/USER-FLOW-GUIDE.md) — load it. **Every output MUST conform.** Violating a rule is a defect, not a stylistic choice.

Key constraints from the guide (non-exhaustive — read the full doc):
- Use ONLY the 6 standard shapes: stadium `([…])`, rectangle `[…]`, diamond `{…?}`, parallelogram `[/…/]`, subprocess `[[…]]`, cylinder `[(…)]`
- One direction per flow (`TD` default, `LR` only when >8 nodes or wide branching)
- Single `Start` + at least one `End`. No dead-end branches
- Decision labels end with `?`. Every branch labeled `-- Yes -->` / `-- No -->`
- Sentence case in all labels. Verbs in actions. Questions in decisions
- 7±2 rule: 5-9 nodes per flow. Excess → extract `[[Subprocess]]`
- No emojis, no HTML, no Title Case, no ALL CAPS in labels
- Max 3 swimlanes per flow

### Step 3 — Invoke supporting skills
- `craft-connect-flow` skill (from `./.claude/skills/craft-connect-flow/SKILL.md`) — for screen-to-screen navigation patterns, shared state, entry/exit points, deep links
- `design-generate-userflow` skill (if present in `./.claude/skills/`) — the canonical source of the 18 rules; identical to the in-repo guide

### Step 4 — Generate the Mermaid flowchart

Produce a fenced Mermaid block following the standard output format:

````markdown
**User flow: [actor] → [goal]**

```mermaid
flowchart TD
  Start([Entry point]) --> A[First action]
  A --> Decision{Decision question?}
  Decision -- Yes --> B[Path A]
  Decision -- No --> C[Path B]
  B --> End([Success state])
  C --> End
```

**Summary:** [2-3 sentences: who the flow serves, main happy path, key decision points.]

**Assumptions:** [List assumptions if input was incomplete. Skip if none.]
````

For multi-actor flows, use `subgraph` swimlanes (max 3 lanes; if more, decompose).

### Step 5 — Validate against the 18 rules

Run the validation checklist from `USER-FLOW-GUIDE.md` §7. Each violation is a defect — fix before delivering. Examples:
- Exactly one `Start` node?
- All paths terminate at an `End` node?
- Every decision label ends with `?`?
- Every branch has `-- label -->`?
- Node count 5–9 (or subprocess for excess)?
- No Title Case / ALL CAPS in labels?
- Mermaid syntax valid (no unclosed brackets, no undefined nodes)?

### Step 6 — Generate the user-stories checklist
Below the Mermaid block, render a numbered list of one user story per flow path:

```markdown
1. **<Story title> (P1)** — <JTBD> [Story 1 in spec.md]
   - Path: <entry> → <action> → <action> → <outcome>
   - Test checklist:
     - [ ] <acceptance scenario 1>
     - [ ] <acceptance scenario 2>

2. **<Story title> (P2)** — <JTBD>
   ...
```

The checklist doubles as the **future testing checklist** (per Tab 3 guardrail #2 in [`03-data-flow.md`](../../docs/03-data-flow.md) §3.1).

### Step 7 — Write to Tab 3 of `template.html`

Update both:
1. The Mermaid block goes into a `<div class="mermaid">…</div>` inside the User Flow tab body (mermaid.js renders it client-side; the template already loads mermaid via CDN)
2. Set `state.flowPopulated = true` (or `PB_DATA.flow.populated = true` in the extension-shipped template) to flip Tab 3 from empty state to populated view
3. Write the user-stories checklist below the diagram
4. Preserve all other tabs

## Confirm to user

```
✅ Tab 3 (User Flow) updated.
   Flow: N nodes, M edges (Mermaid `flowchart TD`)
   User stories: K stories (P1: a, P2: b, P3: c)
   Test checklist items: T
   Rules validation: all 18 passed

Drift check: skipped (Tab 3 is decoupled by design)
```

## Important rules

- **NEVER violate any of the 18 enforced rules** in [`USER-FLOW-GUIDE.md`](../../docs/USER-FLOW-GUIDE.md). Each violation is a defect to fix before delivery, not a stylistic option.
- **NEVER run drift check from /sync-flow** — Tab 3 is decoupled and trio principles don't constrain user-flow representation.
- **NEVER auto-trigger this from /build** or any other command. Only the user invokes /sync-flow.
- **NEVER omit the user-stories checklist** below the diagram — the checklist is what makes Tab 3 testable.
- **NEVER use external font files** in the diagram — Mermaid uses the page's font stack by default.
- **NEVER use emojis, HTML, Title Case, or ALL CAPS** in node labels.
- **NEVER mix flow directions** — pick TD or LR per flow and stick to it.
