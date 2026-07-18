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
   `registry.json` only on `/pb:build --render` and automatically at hand-off / validate —
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
