# Upgrading to Product Builder 2.0

**Read this if you have a working pb project on any 1.x version.** Five steps, and the only one
that touches your project is step 3 — which backs up `registry.json` before it writes and can be
rolled back with one command.

2.0 is a major for exactly one reason: **twelve commands were merged into the twelve that remain,
and the old names were deleted rather than aliased.** Nothing else about your project breaks. Your
registry, render bodies, spec sidecars, logic contracts and memory files all carry forward.

For how pb's three version layers relate to each other, see [upgrading.md](upgrading.md). This page
is just the 1.x → 2.0 move.

---

## 1 · Update the plugin

```
/plugin marketplace update product-builder
```

Then **restart Claude Code** so the new command files load. If a same-name marketplace collision
blocks the new version, do the long form: uninstall the plugin → remove the marketplace → re-add
the source → install.

Confirm you are on 2.0 before going further — `/pb:preview`'s startup banner and the prototype's
meta-nav badge both read `pb v2.0.0`.

## 2 · Rename your commands

This is the breaking half. Every retired name is gone, not redirected, so an old name now just
reports that no such command exists. Nothing in your project stores these names — they live in your
habits, your notes and your team's docs.

| You used to run | Run this now |
|---|---|
| `/pb:flow` · `/pb:sync-flow` | `/pb:plan --flow` |
| `/pb:data` · `/pb:sync-erd` | `/pb:plan --data` |
| `/pb:check-drift` | `/pb:test --drift` |
| `/pb:validate` | `/pb:handoff --tier=host` |
| `/pb:preview-ds` | `/pb:preview`, then open the `/design-system` route |
| `/pb:build-check-design-system` | `/pb:build` — it is now §3a of the build loop, automatic |
| `/pb:build-figma-handoff` | `/pb:handoff` → mode 3 (Figma) |
| `/pb:handoff-close` · `/pb:hand-off` | `/pb:handoff` → mode 1 (everything) |
| `/pb:handoff-dev` | `/pb:handoff` → mode 2 (engineering) |

Two of these are worth knowing beyond the rename:

- **`/pb:handoff` now asks who is receiving the work** instead of taking a sub-command. One
  command, three modes. `--people` / `--context` / `--tier=host` still narrow it if you already
  know what you want.
- **You mostly stop running `/pb:plan --flow` and `--data`.** They are first-time authoring only.
  After a structural change, `/pb:build` reconciles the `flow` and `erd` slices in the same turn.

Coming from a pre-1.5 project, one more: `/pb:migrate` became `/pb:update-version`, which is what
you run next.

## 3 · Update the registry

```
/pb:update-version              # dry run — prints the plan, writes nothing
/pb:update-version --apply      # does it
```

This walks your project from whatever `meta.schemaVersion` it is on up to **12**, one step at a
time, and backs up `registry.json` first.

**One step moves data, so it is worth knowing about.** Step 0010 takes each entry in
`meta.tradeoffs[]` and rewrites it as an `ia.rules[]` rule carrying the `decision{}` it was made
by. A trade-off *is* a rule, so it now lives beside the other rules in **UX Design → Logic**
instead of on its own Project Summary sub-tab. `meta.tradeoffs` stays in the registry as `[]` —
emptied, not removed — so nothing reading the old field crashes.

If your project is several versions back, the dry run lists every step it will take. Read it before
applying.

## 4 · Re-render

```
/pb:build --render
```

Your `prototype.html` was rendered by the old shell and will keep showing the old UI until you
re-render — this is the single most common "the upgrade didn't take" symptom. If `/pb:preview` is
running, restart it instead; it re-renders in memory on the way up.

## 5 · Check it worked

- `/pb:test --drift` reports no shell drift.
- The meta-nav badge reads `pb v2.0.0`, and `prototype.html` opens with
  `<!-- pb-shell v2.0.0 · rendered … -->`.
- Your trade-offs appear under **UX Design → Logic**, alongside the rules.
- `/pb:test` runs clean.

---

## If something goes wrong

```
/pb:update-version --rollback
```

Restores the pre-update `registry.json` from the backup step 3 took, and re-renders. It is a **file
restore, not a reverse migration** — so run it *before* you do more work. Anything you changed after
the migration is in the newer file and goes with it. Backups are never deleted; they pile up in
`.pb-backups/`.

If you have already built on top of the migration and want to step *down* a schema version without
losing that work, use the downgrade path instead:

```
/pb:update-version --to 11        # dry-run first, as always
```

That runs the real reverse migrations. Step 0010's reverse is deliberate about your edits: a rule
you have since edited by hand is left in `ia.rules[]` rather than being folded back into
`meta.tradeoffs[]`.

Nothing in this upgrade deletes a registry field. `meta.tradeoffs`, `meta.others` and `staleness`
are all emptied and kept, per [AGENTS.md](../AGENTS.md) §3 — removal waits for a future major.

## What else is new in 2.0

Not required reading to upgrade, but it changes how two commands behave:

- **`/pb:test` plans the run, then delegates the grading.** It writes a yes/no test plan to
  `memory/test-plans/` and hands it to `pb-tester` subagents that never saw the design being built,
  so a verdict is not written by the context that authored the thing under test. `--no-delegate`
  self-grades and says so.
- **`/pb:build` keeps `flow` and `erd` in sync** after any trio-touching patch — see step 2.
- **UX Design has five segments**, adding Test Cases and Content (a glossary plus the canonical
  wording for every action, status and message).
- **`/pb:explore` scores alternatives against a rubric** rather than asking which one you like.

The full list is in the [changelog](../changelog.md).
