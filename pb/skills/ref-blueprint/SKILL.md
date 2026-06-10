---
name: ref-blueprint
description: Screen-level design thinking for Product Builder. Use BEFORE building or restructuring a screen — loaded by /pb:clarify and useful in /pb:build — to define the screen's Job To Be Done (JTBD), justify every component against that job, and enforce a balanced visual hierarchy. This is the "why" layer for a screen; think-layout is the "how" layer. Not for component-level construction (use design-component-build) or cross-screen navigation (use craft-connect-flow).
---

# ref-blueprint

Before a screen earns any components, it earns a **reason to exist**. This skill keeps each screen
single-purpose and every element on it justified — the antidote to cluttered, do-everything pages.

## 1 · Name the JTBD
One sentence: *"When <situation>, the user wants to <motivation>, so they can <outcome>."* If a screen has
two unrelated JTBDs, it is two screens — split it (constitution principle: one job per screen).

## 2 · Justify every component against the JTBD
List the components the screen will hold. For each, answer: **does this directly serve the JTBD?**
- **Yes** → keep it; note which part of the job it serves.
- **Indirectly** → demote it (smaller, lower, or behind a disclosure) or move it to another screen.
- **No** → cut it. A prototype screen with decorative or "might-need-it" elements fails its job.

## 3 · Balance the hierarchy
- Exactly **one** primary action per screen; everything else is secondary/tertiary.
- The eye should land on the JTBD's main input/decision first (size, weight, position, contrast).
- Group related elements; separate unrelated ones. No competing focal points.

## Output
A short blueprint: the JTBD line, the justified component list (with keep/demote/cut), and the intended
hierarchy (primary → secondary → tertiary). Hand structure decisions to `think-layout` and component
construction to `design-component-build`.

## Rules
- **No component without a job.** If you can't tie it to the JTBD, it doesn't belong.
- **One primary action.** Two primaries means the screen hasn't decided what it's for.
