---
name: agent-orchestrate-tasks
description: Decompose a multi-step Product Builder request into an ordered, trackable task plan — clarify intent, break it into subtasks, sequence them, and define each task's acceptance + which skill it invokes. Use when planning a build — loaded by /pb:plan — so a feature becomes a per-tab task breakdown rather than an ad-hoc scramble. Not for executing a single build patch (use /pb:build) or critiquing requirements (use think-critique-prd).
---

# agent-orchestrate-tasks

Turn "build this" into a concrete, ordered plan. The job is to clarify, decompose, sequence, and define
done — not to do the building.

## 1 · Clarify the goal
Restate what is being built in one line and confirm scope. If intent is ambiguous, run `think-clarify`
first — don't plan against a guess.

## 2 · Decompose by tab, then by task
Group work by where it lands — the 4 prototype tabs (Prototype · Project Summary · UX Design · Data) plus
the **design-system site** (components). Within each, list discrete tasks. A good task is one coherent
change to one slice (a screen, a component, a flow).

## 3 · For each task, define
Emit **every** field below on each task (all are consumed downstream — `deps:` / `slice:` / `agent:` drive
`/pb:orchestrate`'s waves; absence of the new three is tolerated but incomplete):
- **acceptance** — the testable condition that says it's done (e.g. "empty submit shows an inline error").
- **skill** — which skill the executor invokes (`think-layout`, `think-logic`, `design-component-build`,
  `craft-connect-flow`, …).
- **agent** — which of the 8 `pb-*` agents runs it: `pb-clarifier` · `pb-planner` · `pb-builder` ·
  `pb-design-system` · `pb-flow` · `pb-data` · `pb-tester` · `pb-reviewer`. Route by `slice` (below):
  screen / logic → `pb-builder`; component / tokens → `pb-design-system` (or `pb-builder` for a plain build);
  flow → `pb-flow`; erd → `pb-data`; meta → `pb-clarifier`.
- **deps** — comma-separated task ids that must finish first, or `none` (atoms before the molecules that
  compose them, screens before flows). This is what `/pb:orchestrate` topologically sorts into waves.
- **slice** — the one registry slice this task touches: `screen` · `component` · `logic` · `tokens` ·
  `flow` · `erd` · `meta`. One coherent slice per task.

## 4 · Sequence
Order tasks so dependencies come first and the prototype is runnable at each checkpoint. Prefer a thin
end-to-end slice early (one working screen) over many half-built ones.

## Output
A per-tab task breakdown — each task with **acceptance · skill · agent · deps · slice** — ready for
`/pb:plan` to record, `/pb:build` to execute one slice at a time, and `/pb:orchestrate` to run in waves.

## Rules
- **Plan, don't build** — this skill produces the breakdown; `/pb:build` does the work.
- **Every task has acceptance** — no task without a testable done condition.
- **Smallest runnable slices** — keep the prototype rendering at every step.
