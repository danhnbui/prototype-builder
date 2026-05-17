---
description: Generate or update Tab 3 (User Flow). Produces an inline SVG flow diagram + a numbered list of user stories that act as the test checklist. Tab 3 is decoupled — never auto-triggers.
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

### Step 2 — Invoke craft-connect-flow skill
The `craft-connect-flow` skill (from `./.claude/skills/craft-connect-flow/SKILL.md`) defines: navigation patterns, shared state, entry/exit points, transitions, deep links. Use its conventions.

### Step 3 — Generate SVG flow diagram
Produce an inline SVG with:
- **Nodes**: rectangles for screens, diamonds for decisions, circles for entry/exit
- **Edges**: arrows labeled with user actions
- **Grouping**: optional `<g>` clusters per user story (visually distinguishable but readable as one diagram)
- **Scale**: viewBox sized so the diagram fits in a 1200px-wide container without overflow; nodes use the DS font

Keep the SVG self-contained — no external font references, no `<style>` blocks that conflict with the parent page.

### Step 4 — Generate the user-stories checklist
Below the SVG, render a numbered list of one user story per flow path:

```markdown
1. **<Story title> (P1)** — <JTBD> [Story 1 in spec.md]
   - Path: <entry> → <action> → <action> → <outcome>
   - Test checklist:
     - [ ] <acceptance scenario 1>
     - [ ] <acceptance scenario 2>

2. **<Story title> (P2)** — <JTBD>
   ...
```

The checklist doubles as the **future testing checklist** (per Tab 3 guardrail #2 in [03-data-flow.md](https://github.com/danhnbui/spec-kit-extension-prototype-builder/blob/main/docs/03-data-flow.md) §3.1).

### Step 5 — Write to Tab 3
Replace the Tab 3 content block in `./prototype/template.html`. Preserve all other tabs.

## Confirm to user

```
✅ Tab 3 (User Flow) updated.
   SVG flow: N nodes, M edges
   User stories: K stories (P1: a, P2: b, P3: c)
   Test checklist items: T

Drift check: skipped (Tab 3 is decoupled by design)
```

## Important rules

- **NEVER run drift check from /sync-flow** — Tab 3 is decoupled and trio principles don't constrain user-flow representation.
- **NEVER auto-trigger this from /build** or any other command. Only the user invokes /sync-flow.
- **NEVER omit the user-stories checklist** below the SVG — the checklist is what makes Tab 3 testable.
- **NEVER use external font files** in the SVG — embed via the DS font stack only.
