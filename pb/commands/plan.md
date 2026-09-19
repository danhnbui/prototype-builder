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

## 1b · Map jobs to screens

If `registry.ia.jobs[]` is populated (seeded by `/pb:init`), fill each job's `screens[]` with the
screen ids that serve it. A job may be served by several screens, and a screen may serve several
jobs — neither is a problem.

Two outcomes are worth saying out loud in the plan rather than leaving for someone to notice:

- **A job no screen serves** is scope the plan has not covered. List it, and either plan a screen for
  it or fold it into one explicitly.
- **A screen no job points at** is a screen nobody has justified. Ask whether it is needed.

Also link the two directions: give each `flow.stories[]` entry a `jobs[]` list of the ids it
exercises, so a flow path and a standing need reference each other. Leave the story's prose `jtbd`
untouched; it is a narrative, and a job is a standing need — they are not the same thing.

## 2 · Task breakdown (grouped by tab)
Invoke `agent-orchestrate-tasks`. Produce `memory/tasks.md` — tasks grouped by the 4 prototype tabs
(Prototype · Project Summary · UX Design · Data) **plus the design-system site** (where components land).
**Each task** lists:
- **acceptance** — how you'll know it's done.
- **skill** — which skill the build step invokes (`think-layout`, `think-logic`,
  `design-component-build`, `craft-connect-flow`, …).
- **agent** — which of the 8 `pb-*` agents runs it (`pb-clarifier`, `pb-planner`, `pb-builder`,
  `pb-design-system`, `pb-flow`, `pb-data`, `pb-tester`, `pb-reviewer`) — routed by `slice`.
- **deps** — comma-separated task ids that must finish first, or `none` (what `/pb:orchestrate` sorts into waves).
- **slice** — the one registry slice it touches: `screen` · `component` · `logic` · `tokens` · `flow` · `erd` · `meta`.

These five per-task fields are what `/pb:orchestrate` reads to dispatch each task to its agent in dependency
waves. Bake in the sync rules: the **trio** auto-syncs on `/pb:build`; Flow / Data / handoff-screen are manual
(`/pb:flow`, `/pb:data`).

## Result
`memory/plan.md` + `memory/tasks.md` (per-tab tasks with acceptance · skill · agent · deps · slice).
Next: `/pb:build` (one slice at a time) or `/pb:orchestrate` (run the whole plan in agent waves).

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
