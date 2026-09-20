# AGENTS.md — build guardrails for prototype-builder

These are hard constraints for any agent (Claude Code or otherwise) working in this
repo. They exist so pb keeps its token economics, never breaks an existing project, and
stays reviewable. They **override** convenience. If a task cannot be done without
violating one, stop and ask the human partner — do not work around it.

Target build order lives in the release plan; full target state in `pb-full-picture.md`.
This file is the *how you must work*, release-independent.

## 1. Never violate the three load-bearing rules

1. **State lives in `registry.json`.** The loop reads/edits only the touched slice.
   `prototype.html` is **never** the source of truth and is **never** hand-edited.
2. **Batched, deterministic render.** `render.py` regenerates `prototype.html` from
   `registry.json` only on `/pb:build --render` and automatically at `/pb:handoff` —
   never per tweak, never by the model hand-emitting HTML. `/pb:preview` renders through the
   **same generator** in memory (~0 model tokens).
3. **Gate-skip on non-trio tweaks.** The drift / Stack / DS gate runs only when a change
   touches the trio — a screen, a component, or logic. Pure cosmetic tweaks skip it.

## 2. Never break an existing project

- **Every rename ships a backward-compat alias plus a migration.** A renamed command keeps
  the old name working (alias file/stanza); a renamed tool keeps the old import working
  (shim). An existing project on the old names/paths must keep running untouched.
- Aliases are removed only in a later major release, never in the release that introduces
  the rename.

## 3. Additive schema only

- Schema changes are additive. To change the registry/template contract:
  1. Bump `CURRENT_SCHEMA` in `pb/migrations/manifest.py`.
  2. Ship a migration in `pb/migrations/` (`NNNN_<slug>.py`) with a `describe()`.
  3. Wire it into `pb/migrations/migrate_runner.py`.
  4. Prove it: run `/pb:update-version --apply` on a *copy* of an old project and confirm
     it migrates cleanly, then confirm rollback restores the backup.
- Never remove or repurpose an existing field in place. Add, then deprecate later.

## 4. One release per branch, one PR, human merges

- One release → one branch (`release/vX.Y[.Z]`) → one PR. No autonomous `git push` or
  `git merge`. A human reviews the diff and merges — that is the gate.
- Tests are green **before** the PR is opened.
- Keep `CLAUDE.md`, `prototype-builder.md`, and `changelog.md` updated **in the same PR**
  as the code they describe.

## 5. Match pb conventions

- Commands are native `.md` files in `pb/commands/` (invoked `/pb:*`). No SpecKit, no
  `extension.yml` / `preset.yml`, no `after_*` hooks.
- Agents (`pb/agents/*.md`) return **slice patches**; the coordinator applies them serially
  and renders once per wave.
- `render.py` stays **deterministic** — no model calls, no randomness, same registry →
  same HTML.
- Skills are capability-named and **reused**, not duplicated. Prefer an existing skill over
  a new one.

## 6. Verify before wiring

- Skill-to-command links beyond the ones already documented are **inferred**. Before a
  command depends on a skill, read its `SKILL.md` and confirm the contract.
- Before depending on a tool's behavior, read the tool. Do not assume a signature.

## 7. Work task by task

- Do one numbered task at a time, in order. After each task run the relevant check before
  moving on:
  - `pb/tools/lint_registry.py` (registry lint)
  - `/pb:update-version` dry-run (migration plan)
  - `tests/` (repo tests)
  - `pb/tools/test_run.py` (sandbox, when the change is previewable)
- Do not mark a task done while a check is red. When blocked, stop and ask — don't guess.
- **Run the sweep with Playwright, or four tests silently do nothing.** `e2e_smoke.py`,
  `test_inspect.py`, `test_sandbox.py` and `verbs_browser.py` exit **2** (a clean skip) when
  Playwright is absent, so a sweep without it reports green while asserting nothing about the
  shell in a browser. That gap let an increment delete a selector `test_sandbox.py` depended
  on and still ship "all green". Set it up once — the venv is gitignored:

  ```
  python3 -m venv .venv && .venv/bin/pip install playwright && .venv/bin/playwright install chromium
  for f in tests/*.py; do .venv/bin/python "$f"; done     # 31 pass / 0 skip / 0 fail
  ```

## 8. The user's stated goal is the contract

- **Restate before you start.** Open structural work by restating the goal in the user's own
  terms — one or two sentences. Where your restatement and the request differ, **the request
  wins**; do not proceed on a restatement the user has not seen.
- **Never silently re-scope.** Narrowing ("I'll do the simple half"), widening ("while I was in
  there"), and substituting ("what they really need is") are all scope changes. Propose them and
  get an answer. A scope change assumed is a scope change that ships wrong.
- **Record it where the pipeline can check it.** The goal goes verbatim into `memory/prd.md`
  under `## Goal` (or the task's `what:` for a single task). Every later stage is checked against
  **that text**, not against the previous stage's output — otherwise drift compounds silently,
  one stage at a time, and each step looks reasonable next to the one before it.
- **Blocked ≠ done.** If part of the goal cannot be met, finish everything else in full and say
  plainly what was left out and why. Scaling the goal down is the user's call, not yours.

## 9. Structural work runs the discovery pipeline, gated twice by a human

**Applies to:** a new feature, a new flow, a revamp, a new entity, anything touching the trio
(a screen, a component, logic) at structural scale. **Does not apply to:** point fixes, token
values, copy, prop defaults, spacing — those take `/pb:build` directly, exactly as rule 1's
gate-skip says. Do not make a two-line change bureaucratic.

**Hosted by `/pb:explore "<goal>"`** (Mode B — `pb/commands/explore.md`, stages B1–B8); the
canonical summary is CLAUDE.md § *Goal fidelity + the gated discovery pipeline*. Stages run **in
order**. Sub-agents work in parallel **within** a stage, never across stages, and the team is the
existing 8-role roster (rule 5) — no ad-hoc agent types.

| # | Stage | Command · agent | Produces |
|---|---|---|---|
| 1 | **Clarify JTBD** | `/pb:clarify` · `pb-clarifier` | `ia.jobs[]` — three fields each (`when` / `want` / `so`), `roles[]`, `priority`; `ia.layers[]` purposes |
| 2 | **G-JTBD** | — **human gate** — | approval, edits, or rejection |
| 3 | **Discover** | read-only · `pb-clarifier` | findings over the current registry slices, `memory/`, the DS reference + `.source.json`. **No patch** |
| 4 | **Diverge** | N × `pb-builder` via the Task tool (`explore.md` B4) | parallel *approaches* — which screens, what is reused, what is new — compared against the `## Goal` text; one recommended. Form-divergence on a target that already exists is `/pb:explore <id>` (Mode A) instead |
| 5 | **Design** | `/pb:plan` · `pb-planner` | per-task `acceptance · skill · agent · deps · slice` |
| 6 | **G-DESIGN** | — **human gate** — | approval, edits, or rejection |
| 7 | **Build + test** | `/pb:orchestrate` → `/pb:test` · `pb-tester` → `pb-reviewer` | dependency waves, each gated on tester + reviewer; a red gate stops the loop |
| 8 | **Update the documents** | coordinator | `ia.rules` (logic rules) · `memory/prd.md` · `memory/spec.md` · `logic/**` contracts · an entry in `memory/decisions.md` · `DESIGN.md` when an invariant moved |

**No document write before both gates pass.** Stage 8 is the only stage that updates `ia.rules`
or the PRD, and it does not begin until G-JTBD and G-DESIGN are both approved. Stages 1–7 may
write registry slices the plan calls for; they may not rewrite the documents that record intent.

### What makes a gate real

- **Blocking.** Stop and ask. Silence is not approval, and neither is an absent objection.
- **Present the artifact, not a summary of it.** G-JTBD shows every job as `when / want / so`
  and names the jobs mapped to no screen. G-DESIGN shows the option kept *and the ones rejected*,
  the task breakdown, and exactly which documents stage 8 will change.
- **Carry the open questions up.** A gate that hides its uncertainty to look finished is worse
  than no gate.
- **Approval is recorded** — in the `decisions.md` entry stage 8 writes — so a later stage cites
  it instead of re-asking.
- **A rejection returns to the stage that produced it**, not to the start. Re-running a stage
  re-opens its gate; an approval does not survive the artifact it approved.
