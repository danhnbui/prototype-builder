# Tasks: [FEATURE]

**Spec**: `/specs/[###-feature-name]/spec.md` | **Plan**: `/specs/[###-feature-name]/plan.md` | **Date**: [DATE]

---

## How to read this file

- Tasks are grouped by the **tab** they write to.
- **Trio tabs (1, 2, 4-C) auto-sync** on `/speckit.prototype-builder.build` and on `/speckit.constitution|specify|clarify|plan`.
- **Decoupled tabs (3, 4-S, 5) require explicit commands**: `/speckit.prototype-builder.sync-flow`, `.handoff`, `.sync-erd`.
- Each task lists the **skills** it invokes from `./.claude/skills/`.
- Any task marked `[P]` can be parallelized with siblings.

---

## Tab 1 — Prototype (live, auto-sync)

- [ ] **T1.1** — [task description tied to a user story]
  - Skills: `think-layout`, `think-logic`
  - Acceptance: [testable condition]

- [ ] **T1.2** — [task]
  - Skills: [list]
  - Acceptance: [test]

---

## Tab 2 — Project Summary (live, auto-sync)

Tab 2 sub-sections:

### 2.1 Overview
*Auto-populated from spec.md + constitution.md.*

### 2.2 User Insights
*From clarify.md → User Insights section.*

- [ ] **T2.1** — Confirm user insights are reflected accurately
  - Skills: `ref-blueprint`

### 2.3 UI Logic Trade-offs
*From clarify.md → UI Logic Trade-offs section.*

- [ ] **T2.2** — Capture any trade-off decisions surfaced during /build
  - Skills: `think-clarify`

### 2.4 Others
*Reserved per project.*

---

## Tab 4-Component — Design Handoff: Component view (live, auto-sync)

- [ ] **T4C.1** — Build [organism name] with [N] variants
  - Skills: `design-component-build`
  - Acceptance: All variants render in Tab 4-C with live preview

- [ ] **T4C.2** — [organism]
  - Skills: [list]

---

## Tab 3 — User Flow (manual `/sync-flow`)

- [ ] **T3.1** — Generate SVG flow for [feature]
  - Triggered by: `/speckit.prototype-builder.sync-flow`
  - Skills: `craft-connect-flow`
  - Acceptance: SVG renders in Tab 3; one user story per flow path

---

## Tab 4-Screen — Design Handoff: Screen view (manual `/handoff`)

- [ ] **T4S.1** — Generate Screen handoff for [screen name]
  - Triggered by: `/speckit.prototype-builder.handoff`
  - Skills: `design-critics`
  - Acceptance: 7:3 split renders; right panel shows tokens + sizing only (no code)

---

## Tab 5 — ERD (manual `/sync-erd`)

- [ ] **T5.1** — Generate Mermaid `erDiagram` for [entities]
  - Triggered by: `/speckit.prototype-builder.sync-erd`
  - Skills: none (ERD guardrails apply)
  - Acceptance: All 5 ERD guardrails pass or are warned-on

---

## Cross-tab gates

These check-ins fire automatically when `/speckit.prototype-builder.build` runs:

- [ ] **G-DRIFT** — Inline drift check before any trio write — must pass before Tab 1 / 2 / 4-C update
- [ ] **G-DS** — Design system lock check before any styling — triggers G2 on violation
- [ ] **G-STACK** — Stack lock check before any code generation — triggers G3 on violation
