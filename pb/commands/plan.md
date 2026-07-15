---
description: Produce the implementation plan AND the task breakdown, grouped by tab, each task with acceptance criteria + the skill it invokes.
---

# /pb:plan

Produce the implementation plan **and** the task breakdown — grouped by tab, each task with acceptance
+ the skill it uses.

## 1 · Plan
Invoke `ref-prd` (structured context), `think-layout` (structure), `think-logic` (state / rules). Read
`memory/spec.md` + `memory/constitution.md`. Produce `memory/plan.md`: the approach per user story,
honoring the Stack + DS locks.

## 2 · Task breakdown (grouped by tab)
Invoke `agent-orchestrate-tasks`. Produce `memory/tasks.md` — tasks grouped by the 5 tabs
(Prototype · Project Summary · UX Design · UI Design · Data). **Each task** lists:
- **acceptance** — how you'll know it's done.
- **skill** — which skill the build step invokes (`think-layout`, `think-logic`,
  `design-component-build`, `craft-connect-flow`, …).
- **agent** — which of the 8 `pb-*` agents runs it (`pb-clarifier`, `pb-planner`, `pb-builder`,
  `pb-design-system`, `pb-flow`, `pb-data`, `pb-tester`, `pb-reviewer`) — routed by `slice`.
- **deps** — comma-separated task ids that must finish first, or `none` (what `/pb:orchestrate` sorts into waves).
- **slice** — the one registry slice it touches: `screen` · `component` · `logic` · `tokens` · `flow` · `erd` · `meta`.

These five per-task fields are what `/pb:orchestrate` reads to dispatch each task to its agent in dependency
waves. Bake in the sync rules: the **trio** auto-syncs on `/pb:build`; Flow / Data / handoff-screen are manual
(`/pb:sync-flow`, `/pb:sync-erd`).

## Result
`memory/plan.md` + `memory/tasks.md` (per-tab tasks with acceptance · skill · agent · deps · slice).
Next: `/pb:build` (one slice at a time) or `/pb:orchestrate` (run the whole plan in agent waves).

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
