# Prototype Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature spec from `/specs/[###-feature-name]/spec.md`

---

## Summary

[1-paragraph synthesis of what this plan will build, derived from the spec.]

---

## Stack Lock Compliance

The constitution.md locked these at init. Any deviation triggers HITL gate G3.

- **Language**: [from `.specify/memory/constitution.md` Stack Lock]
- **Framework**: [from constitution.md]
- **Design System**: [from constitution.md]

If any item conflicts with this plan → STOP and ask before proceeding.

---

## Tabs Affected by This Plan

Mark each tab this plan will touch. Trio tabs (1, 2, 4-C) auto-sync via `/build`. Decoupled tabs (3, 4-S, 5) require explicit manual sync commands.

- [ ] **Tab 1 (Prototype)** — [what changes]
- [ ] **Tab 2 (Project Summary)** — [auto-syncs from spec/clarify; note any new Principles or Trade-offs]
- [ ] **Tab 3 (User Flow)** — requires `/speckit.prototype-builder.sync-flow` after plan
- [ ] **Tab 4-Component (Design Handoff)** — [organisms/variants touched]
- [ ] **Tab 4-Screen (Design Handoff)** — requires `/speckit.prototype-builder.handoff` after build
- [ ] **Tab 5 (ERD)** — requires `/speckit.prototype-builder.sync-erd` after plan

---

## Skills Invoked

Cite each skill from the cloned `agent-skill-set` repo that this plan will rely on.

- [ ] `ref-prd` — [reason]
- [ ] `think-layout` — [reason]
- [ ] `think-logic` — [reason]
- [ ] `design-component-build` — [reason]
- [ ] `ref-blueprint` — [reason]
- [ ] `craft-connect-flow` — [reason if user flow involved]
- [ ] `design-critics` — [reason if handoff involved]

---

## Implementation Approach

[High-level approach, broken into logical chunks. Reference user stories from spec.md by ID.]

### Per-Story Plan

#### Story 1 (P1)
- Approach: [how]
- Components: [list custom organisms + DS components]
- State/logic: [if any]

#### Story 2 (P2)
- [Same]

#### Story 3 (P3)
- [Same]

---

## Constitution Check

*GATE: Must pass before tasks generation.*

- [ ] No principle in Tab 2 (constitution.md → Principles) contradicted by this plan
- [ ] Stack lock honored (language, framework, DS)
- [ ] DS lock honored (no inline styles, no external CSS imports)
- [ ] Decoupled tabs (3, 4-Screen, 5) not implicitly modified by this plan

If any check fails → STOP, surface the conflict, wait for HITL gate G1/G2/G3 resolution.

---

## Project Structure

```text
my-prototype/
├── prototype/
│   └── template.html          # The 5-tab deliverable (this plan modifies it)
├── design-system/             # Locked at init; read-only
├── .claude/skills/            # Cloned from agent-skill-set
├── .specify/                  # SpecKit runtime (specs, plans, tasks, constitution)
└── docs/                      # This handoff package
```

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., new organism not in DS] | [specific need] | [why existing DS components insufficient] |
