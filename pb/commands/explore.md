---
description: Explore alternatives. With a component/screen id, diverge N render bodies in parallel and let the user score them against a rubric (registry untouched). With a goal sentence, run the gated discovery pipeline — clarify JTBD → discover → diverge → design → build+test → update the documents — stopping at two human gates (G-JTBD, G-DESIGN) before anything is written.
---

# /pb:explore <id | "goal"> [--options N] [--goal] [--target]

Two modes, one verb. **Both are human-in-the-loop** — neither decides for the user.

| You pass | Mode | Diverges on | Registry |
|---|---|---|---|
| a kebab-case id that resolves | **A · target** | the render body of a thing that exists | untouched |
| a sentence / goal text | **B · goal** | the approach, before anything exists | proposed, gated |

## 0 · Pick the mode (do this first)

1. `--target` forces **A**; `--goal` forces **B**. Otherwise:
2. `$ARGUMENTS` is a **single kebab-case token** → resolve it against `screens[]` and `components[]`.
   Resolves → **Mode A**. **Does not resolve → STOP** and say the id is unknown. Never fall through to
   Mode B on an unresolved id — that turns a typo into an eight-stage pipeline.
3. `$ARGUMENTS` **contains whitespace** (a phrase or sentence) → **Mode B**.
4. Empty → ask which they want, with one example of each.

---

# Mode A · diverge one render body

Explore design alternatives for **one** target without touching the registry. Spawn N independent
proposals, preview each, let the **user** choose. Only the pick is promoted; everything else is thrown
away. Writes no registry slice and never renders `prototype.html`.

## A0 · Resolve the target
Record its `kind` (`screen` | `component`), its `renderFn`, and its real body path
(`render/screens/<id>.js` or `render/components/<id>.js`). `--options N` — how many alternatives
(**default 3**). Slots are `opt-1 … opt-N`.

## A1 · Diverge — N candidates in parallel
Invoke the **`ref-design-compare`** skill first: it carries the divergence contract, the generic-tell
ban list, the score sheet and the grades→action mapping. Everything in A1/A2/A4 below is the hook,
not the contract.

**Assign each slot its axis values before launching.** Pick from the seven axes (mental model ·
layout · navigation · component set · motion · hierarchy · contrast) so that every slot differs from
every other on **at least 4 of 7**, and hand each agent *its* assignment. Do **not** launch N agents
on the same brief and hope they diverge — independent agents converge, and the result is one option
in N colours. If two assignments differ on only 2–3 axes, merge them and use the freed slot for
something genuinely different.

Then launch **N `pb-builder` subagents** via the **Task tool**, concurrently (one message, N Task
calls). Each proposes a **full render body** for the target against its assigned axes, with the
**same `renderFn`** and the same public props (so any candidate is a drop-in). Each writes to a
scratch slot:
```
render/_candidates/opt-<k>/<id>.js
```
Give every agent the target's current body, its `renderFn`, its props, and the one-line intent from
`$ARGUMENTS`. Bodies are **token-only** (no raw hex/px — `lint_registry.py`).

## A2 · Preview each candidate in isolation
For each slot, render a standalone preview **on a temporary copy** of `registry.json` whose target entry's
`renderSrc` points at that candidate body (so the real registry is never edited):
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/render.py" <tmp-registry-opt-k.json> \
        "${CLAUDE_PLUGIN_ROOT}/template/prototype.html" render/_candidates/opt-<k>/preview.html
```
One `render.py` run per option → an openable, self-contained preview of just that alternative.

**Look at each one before presenting it — at a desktop width and a phone width.** This is a gate, not
a suggestion (`ref-design-compare` §3): layout bugs are invisible in source and obvious in one
screenshot, and a bare `1fr` grid track sizes to its content rather than its container. Presenting a
candidate you have not rendered yourself is the most common way this goes wrong.

## A3 · Record the options manifest
Write `memory/design-options.json` in the contract shape:
```json
{ "target": "<id>", "kind": "screen" | "component",
  "options": [
    { "slot": "opt-1", "label": "Option 1 — <one-line summary>",
      "axes": { "mental-model": "status", "layout": "columns", "navigation": "top tabs" },
      "bet": "<who this is for, and in what context>",
      "renderSrc": "render/_candidates/opt-1/<id>.js", "renderFn": "<renderFn>" }
  ],
  "rubric": [ { "id": "hierarchy", "label": "Hierarchy", "prompt": "<the question>" } ],
  "scores": { "hierarchy:opt-1": 4 },
  "notes": { "hierarchy": "<what the score meant>" } }
```
One entry per generated slot. `label` is a one-liner of that take; `axes` records the assignment from
A1 so a reviewer can see *why* the options differ; `bet` names the user it is built for. `rubric` /
`scores` / `notes` are filled in A4 — score keys are `"<criterionId>:<slot>"`.

## A4 · Present + score against the rubric
Show the N options — each `label`, its `bet`, the axes it differs on, and the path to its
`preview.html`.

Then ask for a **1–5 score per criterion per option**, plus an optional note per criterion — the ten
criteria in `ref-design-compare` §4, **with 1–2 swapped in or added for whatever this target's intent
said mattered**. Never ask "which do you like?" — a preference cannot be acted on, a pattern of
scores can. Collect it as a markdown table, criteria × options, ending in an **Average** row, and
write the scores back into `memory/design-options.json`.

Read the **pattern**, not the total (`ref-design-compare` §5): the same row low across *every* option
means the standard is wrong, not the options. Then state the verdict **from the scores and notes** —
naming the winner, noting that two options may legitimately lock for different contexts, and giving
**one sentence per rejected option on what it taught**. Do not decide for them; a score sheet with no
verdict is as useless as a verdict with no score sheet.

## A5 · Promote the pick, discard the rest
On a pick:
1. Copy the chosen `render/_candidates/opt-<k>/<id>.js` over the **real** body — overwriting in place.
   `renderFn` / `renderSrc` are unchanged (same names), so `registry.json` needs **no** edit.
2. Delete the whole `render/_candidates/` tree and `memory/design-options.json` (scratch only).
3. Tell the user to `/pb:build --render` (or rely on a running `/pb:preview`) to see it live.

On "none": delete the scratch and leave the real body untouched.

---

# Mode B · the gated discovery pipeline

For a goal that has no component yet — a new feature, a new flow, a revamp. The canonical rules are
**`AGENTS.md` §8–§9**; this is the executable form. Stages run **in order**; sub-agents run in parallel
**within** a stage, never across. The team is the 8-role `pb-*` roster — no ad-hoc agent types.

**Restate the goal first** (§8). One or two sentences, in the user's own terms, shown before any work.
Where your restatement and their request differ, **the request wins**. Write it verbatim to
`memory/prd.md` under `## Goal` — every later stage is checked against *that text*, not against the
previous stage's output.

## B1 · Clarify JTBD — `/pb:clarify` · `pb-clarifier`
Produce `ia.jobs[]`: `when` / `want` / `so`, plus `roles[]` and `priority`. Name the jobs that map to no
screen. Seed `ia.layers[]` purposes — one sentence per layer.

## B2 · ▛ G-JTBD — human gate ▟
**STOP.** Present **every** job as `when / want / so` (not a summary), the unmapped ones called out, and
the open questions. Ask for approval, edits, or rejection. Silence is not approval. Nothing downstream
starts until this is answered; **no document is written yet**.

## B3 · Discover — read-only
Read the current registry slices, `memory/`, the DS reference + `.source.json`. Report what already
covers part of the goal and what conflicts with it. **Produces findings, not a patch.**

## B4 · Diverge — N × `pb-builder`
Launch N subagents concurrently (Task tool), each proposing a **different approach** to the approved
jobs — which screens, which existing components reused, what is genuinely new. Where a target already
exists and the question is form rather than approach, use **Mode A** on it instead of re-deriving it
here.

The **`ref-design-compare`** contract applies here too: assign each approach its axes up front so
they differ on ≥ 4 of 7, and score the approaches rather than eyeballing them. Compare against the
`## Goal` text — never against each other — and recommend one, with a sentence on what each rejected
approach taught. That sentence is what G-DESIGN presents as "the ones rejected, with why".

## B5 · Design — `/pb:plan` · `pb-planner`
Turn the chosen approach into `memory/tasks.md`: per task **acceptance · skill · agent · deps · slice**.

## B6 · ▛ G-DESIGN — human gate ▟
**STOP.** Present the approach kept **and the ones rejected, with why**, the task breakdown, and
**exactly which documents B8 will change**. Ask for approval, edits, or rejection.

## B7 · Build + test — `/pb:orchestrate` → `/pb:test` · `pb-tester` → `pb-reviewer`
Dispatch the plan in dependency waves. `/pb:orchestrate` already gates each wave on `pb-tester` +
`pb-reviewer` and stops the loop on a red gate — do not re-implement that here.

## B8 · Update the documents
**Only now.** `ia.rules` (logic rules) · `memory/prd.md` · `memory/spec.md` · `logic/**` contracts · an
entry in `memory/decisions.md` recording both gate approvals · `DESIGN.md` when an invariant moved.

## NEVER
- NEVER edit `registry.json` in Mode A — it diverges bodies only; the registry stays clean.
- NEVER change a candidate's `renderFn` or props — every option must be a drop-in for the target.
- NEVER leave `render/_candidates/` behind after a decision — promote-then-delete, always.
- NEVER pick for the user, in either mode — present and wait.
- NEVER ask "which do you prefer?" — score against the rubric (`ref-design-compare` §4). A preference
  is not actionable; a pattern of scores names the thing to change.
- NEVER present a candidate you have not rendered and looked at, at both widths (§3 of the contract).
- NEVER launch N agents on one undifferentiated brief — assign the axes first, or they converge.
- NEVER write a document in Mode B before **both** gates pass. B1–B7 may write the registry slices the
  plan calls for; they may not rewrite the documents that record intent.
- NEVER treat an unresolved id as a goal (§0.2), and never re-enter Mode B from inside B4.
- NEVER carry an approval past the artifact it approved — re-running a stage **re-opens its gate**, and a
  rejection returns to the stage that produced it, not to the start.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
