---
description: Execute a whole memory/tasks.md plan by dispatching each task to its fitting pb-* agent in dependency waves — agents return slice patches, the coordinator applies them serially, renders once per wave, and gates each wave on pb-tester + pb-reviewer. Fail-closed on a final strict contract check.
---

# /pb:orchestrate

Run the plan end to end. `/pb:plan` produced `memory/tasks.md` (per-tab tasks, each tagged with
**acceptance · skill · agent · deps · slice**). This command turns that into **dependency waves** and
executes them: each task goes to its fitting agent, agents **return slice patches** (they do not write
the registry themselves), the coordinator applies patches **serially**, renders **once per wave**, then
gates the wave before moving on. Honors the three token levers (`CLAUDE.md`): the compact registry stays
resident, HTML is rendered deterministically once per wave, never per task.

## 0 · Schema check (once)
Apply the **Schema compatibility** check from `CLAUDE.md` **one time** up front, on `registry.json`. If a
pending version update touches a slice the plan will write, **stop** and print
`Blocked: run /pb:update-version --apply first, then retry.` Otherwise print the banner (if any) and proceed.

## 1 · Compute the waves
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/orchestrate.py" memory/tasks.md --json
```
The tool parses every task's `deps:` and topologically groups them into **waves** — wave 1 is every task
with no unmet dependency; each later wave unlocks once its deps' waves complete. It reports each wave's
task ids, their `agent:` and `slice:`. Surface any `ERROR`/`WARN` (a missing dep id, a cycle, an unknown
agent/slice) and **stop on a cycle** — an unschedulable plan can't run.

## 2 · Per wave: dispatch → apply → render → gate
Invoke the **agent-dispatch** skill for the skill/slice→agent mapping and the wave discipline. Then, for
each wave in order:

1. **Dispatch.** Launch every task in the wave via the **Task tool**, one subagent per task, each pointed
   at its `agent:` (one of the 8 `pb-*` roles). Tasks in the **same** wave are independent — dispatch them
   **concurrently** (a single message with multiple Task calls). `deps:` across waves is what sequences
   work; within a wave there are none. Give each agent its task's **what / acceptance / skill / slice** and
   instruct it to **RETURN a slice patch** (the exact registry keys to change + any new/edited
   `render/<kind>/<id>.js` body), **not** to write `registry.json`.
2. **Apply serially.** The coordinator applies each returned patch to `registry.json` **one at a time**
   (never concurrent writes — that races the file), writing any body files. Trio writes still honor the
   `/pb:build` gate (drift / Stack / DS) — a drift PAUSE here bubbles up to the user.
3. **Render once.** After all of the wave's patches are applied, render **exactly once**:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/render.py" registry.json \
           "${CLAUDE_PLUGIN_ROOT}/template/prototype.html" prototype.html
   ```
4. **Acceptance gate.** Dispatch **pb-tester** (run the wave's acceptance conditions / authored scenarios
   via `/pb:test`) and **pb-reviewer** (drift + contract sanity via `/pb:check-drift` + `lint_registry.py`). If the
   gate fails, **stop the wave loop**, report which task/acceptance failed, and hand back to the user — do
   not steamroll into the next wave on a red gate.

## 3 · Final gate (fail-closed)
After the last wave, run the contract validator in strict mode:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/lint_registry.py" --strict registry.json
```
If it exits non-zero, the orchestration **fails** — report the findings; the plan is not "done" until this
is clean (NS6, fail-closed). Exit codes follow the house rule: `0` clean, `1` warnings, `2` any error.

## Result
A built prototype whose `registry.json` reflects the whole `memory/tasks.md` plan, rendered once per wave,
each wave acceptance-gated, and passing a final strict contract check. Next: `/pb:handoff-close` or `/pb:validate`.

## NEVER
- NEVER apply two agents' patches concurrently — serialize every registry write.
- NEVER render per task — render **once per wave** (token lever NS2).
- NEVER skip a wave's acceptance gate or proceed past a red gate.
- NEVER let an agent write `registry.json` directly — agents return patches; the coordinator applies them.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
