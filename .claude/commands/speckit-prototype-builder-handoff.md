---
description: Generate or update Tab 4-Screen (Design Handoff — Screen view). Uses a 7:3 layout per screen; right panel shows DS tokens + sizing only, never code. Runs inline drift check before any trio write.
handoffs:
  - label: Audit Drift Across Trio
    agent: speckit.prototype-builder.check-drift
    prompt: Run a full drift audit across Tab 1, Tab 2, and Tab 4-Component before declaring handoff done.
---

## User Input

```text
$ARGUMENTS
```

If user input names a specific screen, scope to that screen. Otherwise, generate handoff for every screen present in Tab 1.

## Inline Drift Check *(MUST run before any write)*

Same procedure as `/speckit.prototype-builder.build` Steps A–E. Drift check is required because Tab 4-Screen is **derived from Tab 1** — if Tab 1 contradicts a Tab 2 principle, the handoff propagates that contradiction.

If contradictions found → output the exact `⏸ DRIFT DETECTED` block, wait for `yes / no / revise`.

## DS Lock Check *(G2)*

Tab 4-Screen pulls token values directly from `./design-system/tokens.json`. If a screen element uses a value NOT in tokens.json (a raw hex, an inline style), trigger G2:

```
⏸ DS OVERRIDE DETECTED in Tab 1 (source for handoff)

Element: <selector or element name>
Offending value: <e.g., color: #FF00FF (not in tokens.json)>

Extend DS or override this once?  (extend / override / cancel)
```

On `override`, log to `.specify/memory/ds-overrides.log` AND mark the handoff entry with a `⚠ DS override` badge so reviewers see it.

## Write Tab 4-Screen

For each screen in Tab 1:

### Step 1 — Extract elements
Parse Tab 1's HTML for the screen. Identify every distinct UI element (button, input, card, etc.).

### Step 2 — Resolve specs per element
For each element, look up:
- DS token used (color, spacing, font)
- Sizing (width × height in px or rem)
- State (default / hover / active / disabled — if applicable)

### Step 3 — Render the 7:3 layout
Use CSS grid `grid-template-columns: 7fr 3fr`:

- **Left panel (7fr)**: the screen render (interactive), plus annotation badges on each element, plus a "Logic notes" sidebar listing state transitions and validation rules
- **Right panel (3fr)**: the **selected element's spec only**:
  - DS token name and value (e.g., `--brand: #1c4ed8`)
  - Sizing (e.g., `48px × auto`)
  - State (e.g., `default`)
  - NO CODE. NO inline styles. NO component implementation.

Clicking an element in the left panel updates the right panel via a data attribute lookup (handled by the template's existing JS).

### Step 4 — Invoke design-critics skill
Run a critique pass: does the screen handoff convey the design intent without ambiguity? Flag any element whose spec is incomplete.

## Confirm to user

```
✅ Tab 4-Screen handoff generated for N screen(s).

Drift check: passed (or: approved override)
DS overrides: <count> (logged in .specify/memory/ds-overrides.log)

Right panel: tokens + sizing only ✓
Code in right panel: 0 instances ✓ (forbidden by Hard Rule #4)
```

## Important rules

- **NEVER put code, code snippets, or implementation details in the right panel.** Spec tokens + sizing only.
- **NEVER auto-rebuild Tab 1 from /handoff.** /handoff reads Tab 1; it does not write to it.
- **NEVER skip the drift check** — Tab 4-Screen propagates Tab 1's content, so contradictions propagate too.
- **NEVER inline a color, font, or spacing value that isn't in tokens.json.** Always resolve through the DS.
