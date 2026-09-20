---
name: agent-dispatch
description: Route Product Builder tasks to the right pb-* agent and run them in dependency waves — map each task's skill/slice to one of the 8 agents, dispatch a wave concurrently, apply returned patches serially, render once per wave, then gate on pb-tester + pb-reviewer. Use when executing a plan — loaded by /pb:orchestrate. Not for building a single slice by hand (use /pb:build) or decomposing the plan (use agent-orchestrate-tasks).
---

# agent-dispatch

Execute a `memory/tasks.md` plan by handing each task to the agent that fits it and running the plan in
**waves**. The discipline is what keeps a parallel build cheap and correct: dispatch a wave concurrently,
serialize the writes, render once, gate, then move on.

## The 8 agents
`pb-clarifier` · `pb-planner` · `pb-builder` · `pb-design-system` · `pb-flow` · `pb-data` ·
`pb-tester` · `pb-reviewer`.

## skill / slice → agent (route each task)
Route primarily by the task's **`slice:`**, using **`skill:`** as the tiebreaker:

| slice | agent | (skills that land here) |
|---|---|---|
| `screen` | **pb-builder** | `ref-blueprint`, `think-layout`, `think-logic`, `craft-connect-flow` |
| `component` | **pb-design-system** if it's a reuse / variant / naming-contract decision (`build-check-design-system`, `figma-use`); otherwise **pb-builder** (`design-component-build`, `think-layout`) |
| `logic` | **pb-builder** | `think-logic`, `craft-connect-flow` |
| `tokens` | **pb-design-system** | `think-layout` (token schema, no raw hex/px) |
| `flow` | **pb-flow** | `craft-connect-flow` (drives `/pb:plan --flow`) |
| `erd` | **pb-data** | (drives `/pb:plan --data`) |
| `meta` | **pb-clarifier** for Project-Summary copy / insights / trade-offs (`ref-prd`, `think-clarify`, `think-critique-prd`); **pb-planner** for plan / task upkeep (`agent-orchestrate-tasks`) |

`pb-tester` and `pb-reviewer` are **not** slice owners — they run the per-wave acceptance gate (below).

## Wave semantics
A wave is the set of tasks whose `deps:` are all satisfied. `orchestrate.py` computes them by topological
sort: wave 1 = every task with `deps: none` (or only already-done deps); each later wave unlocks when its
deps' waves complete. **Within a wave tasks are independent** → dispatch them **concurrently** (one message,
one Task call per task). **Across waves** `deps:` sequences them → never start a wave before its predecessors
finish and gate green.

## The per-wave loop (invariants)
1. **Dispatch concurrently.** One `pb-*` subagent per task, all in one batch. Hand each its
   what / acceptance / skill / slice, and instruct it to **RETURN a slice patch** (registry keys to change +
   any `render/<kind>/<id>.js` body) — **not** to write `registry.json`.
2. **Apply serially.** The coordinator applies patches **one at a time** to `registry.json` (concurrent
   writes race the file and lose edits). Trio writes still honor the `/pb:build` drift / Stack / DS gate.
3. **Sync once per wave.** After the patches land, the coordinator reconciles `flow` and `erd` **once**
   for the whole wave (`CLAUDE.md` § *Auto-sync*) — from the patches it just applied, never by dispatching
   an agent, never per task. **Skip a slice the wave already owns:** a `flow` (or `erd`) task in the wave
   *is* that slice's sync. Skip entirely when every task was a non-trio slice (`tokens`, `meta`).
4. **Render once per wave.** After all of the wave's patches land and are synced, run `render.py`
   **exactly once**. Never render per task (token lever NS2 — the win is batching).
5. **Acceptance gate.** Dispatch **pb-tester** (`/pb:test` on the wave's acceptance / scenarios) **and**
   **pb-reviewer** (`/pb:test --drift` + `lint_registry.py`). A red gate **stops the loop** — report and hand back;
   do not proceed to the next wave.

## Rules
- **Serialize every registry write** — one patch at a time; agents return patches, they don't write.
- **Render once per wave** — never per task.
- **Sync once per wave** — reconcile `flow`/`erd` after the patches, before the render; skip a slice a
  task in the same wave authored.
- **Gate every wave** — pb-tester + pb-reviewer between waves; never steamroll a red gate.
- **Route by slice first** — skill only breaks the component / meta tie.
- **Final fail-closed** — the plan isn't done until `lint_registry.py --strict` is clean.
