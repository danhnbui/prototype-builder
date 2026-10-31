---
description: Show what this project has piled up — closed explore rounds, backups, orchestrate patches, the decisions log, the preview server's log, screenshots, scratch candidate folders, worktrees — and prune it on request. A dry run by default; nothing is deleted without --apply, and a backup, a closed round or a patch folder only with an explicit --keep-backups / --keep-closed / --keep-patches.
---

# /pb:clean [--apply] [--keep-closed N] [--keep-backups N] [--keep-patches N] [--rotate-decisions]

Everything pb leaves behind grows with use, and nothing expires on its own: every `/pb:explore`
round is archived under `memory/explore/_closed/`, every risky write leaves a folder in
`memory/backups/`, every migration one in `.pb-backups/`, every `/pb:orchestrate` task one in
`.pb-patches/<TASK-ID>/`, `memory/decisions.md` only ever gains entries, and the preview server
appends to `.preview/server.log` for as long as the project lives. This command makes that visible,
and removes it when the user says so. (One real project's `.pb-patches/` reached 122 MB in 65 task
folders; one decisions log was 251 KB of a 500 KB threshold nothing was checking.)

A tool does the counting and the deleting. **Dry run by default.**

## 0 · Flags

| Flag | Does |
|---|---|
| *(none)* | The dry run: a table of what exists and what each flag would do. Changes nothing |
| `--apply` | Do the always-safe set only: remove `render/_candidates/<target>/` folders no open round owns, trim `.preview/server.log` to its last 256 KB when it is over 1 MB, delete `.preview/shots/`. **Never** touches a backup or a closed round on its own |
| `--keep-backups N` | With `--apply`: keep the newest N backups in `memory/backups/`, the newest N in `.pb-backups/` **and** the newest N in `memory/.pb-backups/` (the copies `decisions_rotate.py` takes) — N in each place, not in total — delete the rest. A `registry.<v>.<ts>.json` and its `spec.<v>.<ts>/` snapshot are one backup |
| `--keep-closed N` | With `--apply`: keep the newest N closed explore rounds, delete the rest — each round's manifest, brief and folder together. The newest promoted IA round of each id is pinned (`/pb:plan` reads it) and does not count toward N |
| `--keep-patches N` | With `--apply`: keep the newest N task folders in `.pb-patches/` by modification time, delete the rest. The files at the top of `.pb-patches/` (`BRIEF*.md`) are never deleted, and a task folder that is a symlink is refused |
| `--rotate-decisions` | With `--apply`: run `decisions_rotate.py` on `memory/decisions.md` — whole entries, by date, verified lossless against the original. Under its 500 KB threshold it reports "nothing to do", which is success. If its lossless check fails it restores the original, this command reports it and exits 1 |
| `--json` | The same facts, machine-readable |

N must be 1 or more. A keep flag or `--rotate-decisions` without `--apply` is a preview: it says what
it **would** do and changes nothing.

## 1 · Look first

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/clean.py"
```

Run it from the project root; it finds `./registry.json`, or `./.prototype/registry.json` in an
adopt-in-place project. Exit 2 means there is no registry here: say so and stop.

Show the user the table as it printed. One row per kind of pile, with a count, a size and what the
flags would do:

- **open explore rounds** — each with its age; `STALE` past 3 days. Never touched by this command.
  A round is closed with `explore.py promote <id> <slot>` or `explore.py reject <id>`
- **closed explore rounds**, **`memory/backups/`**, **`.pb-backups/`**, **`memory/.pb-backups/`**, **`.pb-patches/` task folders** — kept unless a keep flag says otherwise
- **`memory/decisions.md`** — its size against the 500 KB rotation threshold. Rotated only by
  `--apply --rotate-decisions`, and only does anything past the threshold
- **`.claude/worktrees/`** — how many and how big. **Report only**: never deleted here, by any flag.
  If the user wants one gone, that is a `git worktree remove` they run themselves
- **`.preview/server.log`**, **`.preview/shots/`**, **`render/_candidates/` with no round** — the always-safe set
- **preview server** — running or not. Never stopped here; `serve.py --stop` stops it

Then say in a sentence what a bare `--apply` would free, and what each keep flag would free if the
user wants more (run the dry run again with the flag to show the exact list).

## 2 · Ask, then apply

Stop and ask before `--apply`. Silence is not approval.

- The user says to go ahead, with no number: run `clean.py --apply` — the always-safe set, nothing else.
- The user names a number for backups or rounds ("keep the last 10 backups"): confirm the dry run for
  that flag (`clean.py --keep-backups 10`), show what it would delete, ask once, then run
  `clean.py --apply --keep-backups 10`.
- The user names a number for patches ("keep the last 10 patch folders"): same dance with `--keep-patches 10`.
  A `.pb-patches/<TASK-ID>/` folder is the record of what an agent returned for that task, so a number
  is the user's to give.
- The user asks to rotate the decisions log: show the row, then run `clean.py --apply --rotate-decisions`.
  It never rotates on a bare `--apply`. Print the tool's own output as it came (what moved, or "nothing
  to do"); a lossless-check failure is reported and the original stays.
- The user gave no number: **do not choose one.** Say which flags exist and what each would free, and
  let them pick. A backup is how `/pb:update-version --rollback` and `/pb:explore` promote are undone.

Print the tool's closing lines as they came: what was removed and the bytes freed. Exit 1 means a path
was **refused** (it resolved outside the project, such as a symlink that leaves the folder) or could not
be removed, or a decisions rotation failed its lossless check (the original stays); the rest was still
done. Name each refused path and leave it to the user.

## 3 · Why the health report names this

`/pb:test` runs the ranked health report (`lint_registry.py --report`), whose `resources` block uses
the same measurements (it imports this tool's scan, so the two lists cannot drift): backups past 20
entries or 50 MB, an explore round open more than 3 days, closed rounds past 50 MB, `.pb-patches/`
past 30 task folders or 50 MB, a decisions log past 500 KB, `server.log` past 1 MB, a registry key
holding more than 35% of the file, a preview server idle for an hour. `.claude/worktrees/` is shown
there too, as a count and a size, and is never ranked. Each line it ranks names the command that fixes
it, usually this one. Thresholds can be overridden in `memory/doctor.json` (`patches_mb`, `patches_count`
among them).

## NEVER
- NEVER pass `--apply` before the user has said yes to this run.
- NEVER pass `--keep-backups`, `--keep-closed` or `--keep-patches` with a number the user did not give.
  There is no sensible default, and a deleted backup cannot be restored.
- NEVER delete a `.claude/worktrees/` entry, or a file at the top of `.pb-patches/` (`BRIEF*.md`), from
  here. The first is git's to remove, the second is the user's brief.
- NEVER pass `--rotate-decisions` unasked, and NEVER run `decisions_rotate.py` by hand instead: the
  tool's invocation is what reports a failed lossless check.
- NEVER delete by hand what the table lists (`rm`, `rm -rf`). The tool checks every path resolves
  inside the project before it deletes, refuses a symlink that leaves it, and never touches an open
  round; a hand-run `rm` checks none of that.
- NEVER stop or kill the preview server from here. `serve.py --stop` does it, only when the health
  check confirms the server is this project's.
- NEVER touch an open explore round, its `memory/explore/<id>/` folder or its candidates, whatever the
  flags. Close it first (`explore.py reject <id>`), after the user decides.
- NEVER edit `registry.json` or a render body. This command only removes derived and archived files.
