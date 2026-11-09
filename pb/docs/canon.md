# Product Builder — the canon

This is the canonical text of Product Builder's operating rules, and it **ships with the plugin**:
commands, agents and skills cite it as `${CLAUDE_PLUGIN_ROOT}/docs/canon.md` § *<section>* rather than
re-stating it, and the plugin's hooks point at it. It travels with every install, so a rule cited from
a command resolves in any project, not only in the repository that develops pb. The sections are the
three token levers, the goal-fidelity pipeline, auto-sync, responsive design, the footprint bounds
and the schema check. A section is edited here and nowhere else.

## The three load-bearing rules (token levers — ship together)

1. **State in `registry.json`.** The loop reads/edits only the touched slice. `prototype.html`
   is **never** the source of truth and is **never** hand-edited. Read a slice with
   `slice.py get <kind> <id>` (locate it first with `slice.py find <text>`; `get` prints at most 8,000
   characters, `--full` lifts the cap); write it with `slice.py set <kind> <id>` — it takes the registry lock.
   A hand-written `json.dump` of `registry.json` bypasses the lock and loses a concurrent write.
2. **Batched, deterministic render.** A generator regenerates `prototype.html` from `registry.json`
   ONLY on `/pb:build --render` and automatically at `/pb:handoff` — **never** per tweak,
   and **never** by the model hand-emitting HTML (that is ~2–3× *worse* — measured at G0.5).
   *(`/pb:preview` may render on every change without breaking this: it's the **same generator**
   rendering **in memory** at ~0 model tokens — never the model, never written to disk unless `--write`.)*
3. **Gate-skip on non-trio tweaks.** The drift / Stack / DS gate runs only when a change touches
   the **trio** — a screen, a component, or logic. Pure cosmetic tweaks skip it.

## Goal fidelity + the gated discovery pipeline

Structural work — a new feature, a new flow, a revamp, anything touching the **trio** at structural
scale — runs one pipeline, hosted by **`/pb:explore "<goal>"`**. Point fixes, token values, copy, prop
defaults and spacing go straight to `/pb:build`, exactly as the gate-skip lever (rule 3) says. Do not
make a two-line change bureaucratic.

**The user's stated goal is the contract.** Restate it before starting; where the restatement and the
request differ, **the request wins**. It goes verbatim into `memory/prd.md` `## Goal`, and every stage is
checked against *that text* — never against the previous stage's output, or drift compounds one
reasonable-looking step at a time. Never silently narrow, widen or substitute scope.

**Eight stages, two stage gates** — plus the gates a stage holds inside it (`/pb:clarify`'s G-IA, diverge's
G-DIRECTION): clarify JTBD (`/pb:clarify` → `ia.jobs[]` as `when`/`want`/`so`) ·
**▛ G-JTBD ▟** · discover (read-only) · diverge (direction **▛ G-DIRECTION ▟** → plans → N × `pb-explorer`) · design (`/pb:plan` → `memory/tasks.md`) ·
**▛ G-DESIGN ▟** · build + test (`/pb:orchestrate` waves, gated on `pb-tester` + `pb-reviewer`) ·
update the documents (`ia.rules`, `memory/prd.md`, `memory/spec.md`, `logic/**`, `memory/decisions.md`).

A gate is **blocking**: it presents the artifact rather than a summary of it, carries its open questions
up, and records the approval. Silence is not approval. **No document is written before both gates pass** —
the stages before may write the registry slices the plan calls for, but never the documents that record
intent. A rejection returns to the stage that produced it, not to the start; re-running a stage re-opens
its gate.

Executable form: `/pb:explore` Mode B (`${CLAUDE_PLUGIN_ROOT}/commands/explore.md`). The rules in full follow.

### The user's stated goal is the contract

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

### Structural work runs the discovery pipeline, gated twice by a human

**Applies to:** a new feature, a new flow, a revamp, a new entity, anything touching the trio
(a screen, a component, logic) at structural scale. **Does not apply to:** point fixes, token
values, copy, prop defaults, spacing — those take `/pb:build` directly, exactly as rule 3's
gate-skip says. Do not make a two-line change bureaucratic.

**Hosted by `/pb:explore "<goal>"`** (Mode B, stages B1–B8). Stages run **in order**. Sub-agents work
in parallel **within** a stage, never across stages, and the team is the existing 9-role roster
(`pb-clarifier`, `pb-planner`, `pb-builder`, `pb-design-system`, `pb-flow`, `pb-data`, `pb-tester`,
`pb-reviewer`, `pb-explorer`) — no ad-hoc agent types.

| # | Stage | Command · agent | Produces |
|---|---|---|---|
| 1 | **Clarify JTBD** | `/pb:clarify` · `pb-clarifier` | `ia.jobs[]` — three fields each (`when` / `want` / `so`), `roles[]`, `priority` (`ia.layers[]` purposes and `meta.navHub` follow in stage 5, once screens exist) |
| 2 | **G-JTBD** | — **human gate** — | approval, edits, or rejection |
| 3 | **Discover** | read-only · `pb-clarifier` | findings over the current registry slices, `memory/`, the DS reference + `.source.json`. **No patch** |
| 4 | **Diverge** | coordinator → **G-DIRECTION** → N × `pb-explorer` via the Task tool, one per execution plan (`explore.md` B4) | parallel *approaches* — which screens, what is reused, what is new — compared against the `## Goal` text; one recommended. Form-divergence on a target that already exists is `/pb:explore <id>` (Mode A) instead |
| 5 | **Design** | `/pb:plan` · `pb-planner` | per-task `acceptance · skill · agent · deps · slice`; the IA pass — jobs → screens, `ia.layers[]` purposes, `meta.navHub` |
| 6 | **G-DESIGN** | — **human gate** — | approval, edits, or rejection |
| 7 | **Build + test** | `/pb:orchestrate` → `/pb:test` · `pb-tester` → `pb-reviewer` | dependency waves, each gated on tester + reviewer; a red gate stops the loop |
| 8 | **Update the documents** | coordinator | `ia.rules` (logic rules) · `memory/prd.md` · `memory/spec.md` · `logic/**` contracts · an entry in `memory/decisions.md` · the project's design-invariants file, when it keeps one and an invariant moved |

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

## Auto-sync — flow + erd ride the trio

The trio classifier (a screen, a component, logic) drives one more thing: after a **trio-touching**
patch, `/pb:build` reconciles the `flow` and `erd` slices **in the same turn**. No Sync button, no
second command. Non-trio tweaks — a token value, a copy reword, a prop default, spacing — **skip it**,
exactly as they skip the gate. Rule 3 is unchanged.

- **Reconcile, never regenerate.** The sync reads the patch it just applied — never `memory/spec.md`
  or `memory/plan.md`. It inserts, deletes and re-points; everything the patch did not touch is left
  exactly as authored.
- **Populated slices only.** `flow.populated` / `erd.populated` false → skip. First-time authoring is
  `/pb:plan --flow` / `--data`; they read the spec, the loop does not.
- **Never re-author.** No rewriting an existing scenario (that discards the `lastResult` `/pb:test`
  wrote), no second five-lens QA pass, no re-deriving an untouched entity.
- **Defer restructuring.** Past 9 nodes, a new flow, a new entity with relationships → stop and name
  the command that owns it. The loop inserts; it does not redesign.
- **No render, no second gate.** The sync writes registry slices only — levers 1 and 2 hold, and the
  gate already ran for the patch itself.
- **One line when it writes, one line when it defers, silent on a true no-op.**

`/pb:build`, `/pb:plan` and `/pb:orchestrate` reference this section rather than re-stating it.

## Responsive across devices

A prototype used to be designed once, at `meta.device`, and shown in every other frame stretched or
squeezed — the laptop frame was the phone column at 1280px with a bottom tab bar. Two causes, both
structural: a render body styles itself inline, and inline `style=""` cannot hold a breakpoint; and the
device frames are `<div>`s in one document, so even a real `@media` rule answered the browser window.

- **Ask once, at `/pb:init`.** Right after *which devices*, ask whether the UI adapts to each of them
  → `meta.responsive`. `true` → designed for every size class in `meta.devices`; `false` → one layout,
  and `meta.devices` is trimmed to `meta.device`. Devices in one size class → not asked (`false`). An
  older project with `null` is asked by `/pb:build` §1b before its next screen/component write — once.
- **Size classes:** **compact** < 600px (mobile) · **medium** 600–1023px (tablet) · **expanded**
  ≥ 1024px (laptop, monitor).
- **Mechanism.** Every place a project renders is a container named `pb-screen` — the prototype's
  `.proto-screen`, the design system's demo stage and variant cells. A
  component/screen that changes across sizes carries `styleSrc` → `render/styles/<id>.css`, scoped to
  its root class (`.c-<id>` / `.s-<id>`), written as **`@container pb-screen (…)` — never `@media`**.
  `product.css` (the plugin's `template/`) adds `r-compact` · `r-medium-up` · `r-expanded-up` ·
  `r-below-expanded` · `r-cols` · `r-measure` for swaps that need no sheet. The `think-layout` and
  `design-component-build` skills carry the authoring contract.
- **Enforced** by `lint_registry.py`: `R-STYLE-MEDIA` (a size `@media`), `R-STYLE-SCOPE`, `R-HEX`/`R-PX`
  in sheets, `R-STYLESRC` (missing file), and `R-RESPONSIVE` — `meta.responsive` `false` across several
  size classes, or `true` with a screen nothing in which adapts (`null` is `/pb:build`'s question, never a
  lint finding — an older project's CI stays green).
- **Looked at.** `think-layout` §5 screenshots every listed size; the expanded frame must not be the
  compact layout stretched.

### Responsive styles

An inline `style=""` cannot hold a breakpoint, so a component or screen that changes across device sizes
carries an optional `styleSrc` → `render/styles/<id>.css`. `render.py` emits `template/product.css` (the
size-class utilities) and then every sheet, components before screens, into one
`<style id="pb-product-css">` in both sites. A sheet styles its own root class,
`.c-<id>` for a component and `.s-<id>` for a screen, and uses **`@container pb-screen (min-width: …)`,
never `@media`**: the device frames are `<div>`s in one document, so `@media` answers the browser window,
not the frame. Utilities: `r-compact` · `r-medium-up` · `r-expanded-up` · `r-below-expanded` (show only in
that range) and `r-cols` (1 → 2 → 3 columns). Anything that changes across sizes lives in the sheet, not
inline: an inline declaration beats the container rule. Lint: `R-STYLESRC` · `R-STYLE-MEDIA` ·
`R-STYLE-SCOPE` · `R-HEX`/`R-PX` · `R-RESPONSIVE` (see `meta.responsive`).

`/pb:init`, `/pb:build`, `think-layout` and `design-component-build` reference this section rather
than re-stating it.

## Checking a change

After a change, use the lowest level that answers the question. A browser is level 2 and up; most
changes never need it. Measured over one month on five real projects: 8,632 UI-check calls, about 28 hours
of waiting and about 17% of spend; check rounds ran a median of 4 calls, p90 21, max 75; Chrome DevTools made
2,750 calls though pb never asks for it; evals outnumbered screenshots 2 to 1, so many checks wanted a fact,
not a picture. A rule that said only "don't open Chrome for every change" changed nothing, so each level
names its tool.

| Level | When | Check |
|---|---|---|
| 0. Trust the reload | Copy, token value, prop default, spacing | Nothing, or lint. The preview reloads in the user's tab. The reply says what changed and that it wasn't looked at. |
| 1. Code check | Any render body or logic edit | `lint_registry.py --exec` (runs every body in node; about 0.4 s on the largest real project) |
| 2. Page facts | Is the text there, is it hidden for this role, any console errors, any overflow | `shot.py --no-png --eval ... --console`, one width |
| 3. One look | A visual change in one place | `shot.py --selector ...`, one width, read one image |
| 4. Full look | A new or restructured screen, and before saying a structural change is finished | Every width in `meta.devices`. A subagent looks and returns a verdict, so images stay out of the main thread. |

- **The levels follow the trio classifier** that already decides the gate: a non-trio tweak is level 0 or 1,
  a trio point edit is level 1 to 3, structural work is level 4. A new or restructured screen is never
  signed off below level 4.
- **Check once per batch of edits**, not after each edit.
- **Every image read stays in context** for the rest of the session, about 1.5k tokens each, and is
  re-read on every later call. `shot.py` takes 4.7 s at the median and 17 s at p90; level 1 takes under a second.
- **Chrome DevTools is for what `shot.py` cannot do** (network or performance debugging), or when the user
  asks for it. It is not how pb looks at a render.
- **A multi-step build belongs in a `pb-builder` subagent**, which starts at about 11k tokens of context
  against a long session's 184k median, so its looks and retries cost far less.

## pb bounds its own footprint (v2.2)

On three real projects in one morning, tests booted their own server and browser 156 of 183 times,
agents hand-wrote ~740 browser scripts, up to 4 headless browsers (~0.6 GB each) ran at once, preview
servers never exited (3 of 4 were orphans), and nothing that grew was ever flagged or pruned. pb now
bounds what it starts and shows what accumulates:

- **At most 3 headless browsers at once, per machine and user.** `tools/browser.py` is the one door
  `test_run.py`, `shot.py`, `explore.py check --shots` and `spec_measure.py` (`/pb:build`'s component
  measuring) open a browser through: a counting semaphore of slot files
  in a per-user temp directory, freed by the kernel when its holder dies. `PB_BROWSER_SLOTS`
  (default 3; `0` = no limit) · `PB_BROWSER_WAIT` (default 120 s). It **fails open**: past the wait it
  prints one `note:` and starts the browser anyway, so the limit is a courtesy and never a reason a test
  cannot run.
- **Tests reuse the running preview.** `test_run.py` with no `--attach` attaches to this project's
  `/pb:preview` when one is up (`reusing the running preview at <url>`) and boots a private server only
  when none is; `--isolated` forces the private one, `--attach [URL]` is as before. `--all` runs
  functional + roles + server in **one** browser — it is how `/pb:test` runs its three browser modes.
- **To look at a render, run `shot.py`.** It reuses the preview (or boots one for the run and stops it),
  opens one browser for every viewport and writes PNGs to `.preview/shots/`:
  ```
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/shot.py" registry.json --screen <id> [--viewport WxH]... [--role <id>] [--console]
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/shot.py" registry.json --path /explore/<id>/<slot>
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/shot.py" registry.json --screen <id> --no-png --eval "<JS>" --console
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/shot.py" registry.json --screen <id> --step click:<CSS> --step fill:<CSS>=<VALUE> --step press:<KEY> --step wait-for:<CSS> --step shot:<NAME>
  ```
  Defaults: 1440x900 and 390x844. `--selector`, `--click`, `--wait-for`, `--eval` and `--full-page` cover
  what a throwaway script was written for. **`--no-png`** takes no image and prints what `--eval` and
  `--console` return: a fact costs a few tokens, a picture about 1.5k that stays in context. **`--step`**
  (repeatable) runs click, fill, press, wait, wait-for, eval and shot in the order given, once per
  viewport, so a flow that needs several moves is one call. Exit `3` = cannot run (no Playwright) —
  *blocked*, not passed. Which of these to reach for: § *Checking a change*.
- **One way to start a preview: `serve.py registry.json --ensure`.** It is idempotent and detached — it
  prints the URL whether it started a server or found this project's running one, so calling it twice is
  harmless and it is also how a stopped preview is restarted. `/pb:preview` and `explore.py link` use it.
- **A preview belongs to no chat session.** Run `--ensure` as a plain (foreground) command: it returns
  once the URL answers and the server lives on, reparented away from the caller. Claude Code stops a Bash
  `run_in_background` task, and every process it started, when the session that started it ends. People
  open and close many short sessions a day to save tokens, so a server tied to one dies in minutes
  ("the server dies after 5 minutes"). A server's life is set by idle time alone.
- **A server a project adds in front of pb** (a router that puts several apps on one origin, a wrapper
  that changes a header) keeps the same contract: one idempotent, detached start command that reuses a
  running copy and prints the URL; an idle exit counted from the last request and held off by any open
  live-reload stream; `--status` and `--stop` that act on the pid the server's own health answer names; a
  record file it removes on exit. It never runs as a background task either.
- **A preview stops itself after 8 hours with no browser tab open and no request** and drops
  `.preview/server.json` (`--idle-exit MINUTES`, `PB_PREVIEW_IDLE_MIN` override it). Do not pass
  `--idle-exit 0`: a server that never exits is how three of four became orphans. Inspect with
  `serve.py --status`, stop with `serve.py --stop`.
- **At most 6 managed previews per user** (`PB_PREVIEW_MAX`, `0` = no cap). Starting another stops the
  longest-idle one that has no open tab — never one with a tab open.
- **Each project gets a stable default port**, derived from its path, so a preview keeps its URL across
  restarts. `--port` wins.
- **The server refuses an unknown `Host` on every route.** To preview from another device or through a
  tunnel, start it with `--allow-host <name>`. `/memory/`, `registry.json` and dot-paths are never served
  as static files.
- **Growth is visible and prunable.** The health report (`lint_registry.py --report`, part of `/pb:test`)
  has a `resources` block that ranks backups, open and closed explore rounds, `server.log` and an
  oversized registry key; `/pb:clean` shows the same piles and prunes them. **Nothing is deleted without an
  explicit keep flag** — `/pb:clean --apply --keep-backups N` / `--keep-closed N` / `--keep-patches N` are the
  only way pb ever deletes a backup, a closed round or a stored patch, and `--rotate-decisions` is the only
  way `decisions.md` is split.

The rules agents follow:

- **NEVER hand-write a Playwright script to look at a prototype** — use `shot.py` (and `test_run.py` to test).
- **NEVER start a server (`serve.py` or one the project adds) with `run_in_background`, `&` or `nohup`, and
  never with `--idle-exit 0`** — `serve.py registry.json --ensure`, run as a plain command, starts or finds it.
  `explore.py link` does the same when it needs one.
- **NEVER `kill` or `pkill` a preview, or hunt for it with `lsof`** — `serve.py --status` finds it and
  `serve.py --stop` stops it; it also exits by itself after 8 idle hours.
- **NEVER write `registry.json` by hand** (`json.dump`, `open(…, 'w')`, a redirect) — `slice.py set`.

**Hooks put the key rules in front of the model, and send the common ones down the safe path.** The
plugin's `hooks/` folder runs small scripts in any pb project (a folder with `registry.json` and a `render/`
folder or `memory/constitution.md`, in the working directory, under `.prototype/`, or in an immediate child
folder). `session_rules.py` prints a short digest of these rules at session start, and `bash_advice.py` adds
one line of advice before a shell command that matches a rule above. `route.py` (`PreToolUse`,
`PostToolUse` and `PostToolUseFailure`) forces a few rules through at call time:

- a built-in generic subagent call (general-purpose, Explore, Plan, claude, or no type) with no `model` gets
  one filled in (haiku for Explore, else sonnet) through `updatedInput`; in `auto` permission mode it only
  advises. Named agents (`pb:*`, another plugin's `x:y`, a project agent) are never touched, and a fork gets
  advice only;
- advice, rate-limited, on parsing `registry.json` inline (use `slice.py find` or `get --fields`), on
  `grep -r`, `rg`, `sed -n` or `cat` of a big file (use the Grep and Read tools), on `touch registry.json`
  (the preview reloads on its own) and on a whole Read of `registry.json`, `prototype.html` or
  `design-system.html`;
- before a hand write of `registry.json` (a Bash write, Edit, Write or MultiEdit) it stashes the file; after
  the write, whether the call succeeded or failed, it checks that the JSON parses, the top-level keys are all
  there and no id is newly duplicated, and restores the stash when the file is broken. As a second net, a later
  hook run in the session puts back a registry that no longer parses from a stash older than 5 s that nothing
  settled (never one written in the last 2 s, while a command may still be running);
- it asks before an edit in a different pb project, a different git work tree or the plugin root (temp
  folders are exempt), and keeps asking for that root until an edit there has gone through: a denied or
  failed edit leaves no mark.

`route.py` never denies a call and never approves one: the only decision it can print is `ask`, which hands
the choice back to the user. `memory/doctor.json` `"enforce"` sets the mode: `route` (default), `advise`
(every rewrite, ask and restore becomes an advice line) or `off`; the environment variable `PB_ENFORCE`
overrides it. What it does is logged to `.preview/route.log`, trimmed to its last 128 KB once it passes
256 KB. Every hook prints nothing outside a pb project. `housekeep.py` (`SessionStart`, and `PostToolUse`
after an edit of `memory/decisions.md`) keeps the files in *Size budgets* below in bounds; it deletes
nothing. `activity.py` runs on `UserPromptSubmit`, `PostToolUse` (so a long turn stays Working) and `Stop`: it prints nothing and writes `.preview/activity.json`
(only where a preview has already made `.preview/`), which is how the open preview knows whether Claude is
working (*Line by line*, below).

## Size budgets

Files that grow are kept in bounds by structure, not by silent rewriting. Nothing here is deleted without a
flag, and nothing is summarised by a model.

| What | Budget | What keeps it there |
|---|---|---|
| `memory/decisions.md` | 500 KB | Rotated automatically and losslessly: older entries move to `decisions-<YEAR>.md` (`decisions_rotate.py`, verified against the original). `/pb:clean --rotate-decisions` still does it on request |
| `.preview/server.log` | 1 MB | Trimmed to its last 256 KB when the preview starts, and by `/pb:clean --apply` |
| `.preview/route.log` | 256 KB | Trimmed to its last 128 KB by `route.py` |
| `registry.json` | no byte cap | Never rewritten for size. Bulk content moves out structurally: migration `0012` moves a `meta.others` that no code reads to `memory/others.md` (one that a render body, `styleSrc` or runtime module reads stays, with the fix named), and `R-INLINE-DATA` keeps data out of render bodies. Reads go through `slice.py find` and `get`, never a whole-file read |
| Render bodies, `styleSrc`, `runtime/` files | a `data:` URI or base64 run under 8 KB | `R-INLINE-DATA` warns, and is an ERROR under `--strict` |
| `memory/*.md` | 64 KB each (`memory_file_kb` in `memory/doctor.json`) | Warned in `lint_registry.py --report`; never auto-summarised |
| Backups, `.pb-patches/`, generated HTML tracked by git | none | Warned only; backups are pruned by `/pb:clean` keep flags alone |

`lint_registry.py --report` shows where the size goes: the registry's bytes and approximate tokens, its five
largest slices, the `memory/*.md` files over budget, the `decisions` sizes and any generated HTML tracked by git.

## Line by line (v2.6)

A command that authors a project used to write its slice in one go at the end, so the open preview sat
empty for minutes and then reloaded. While a command is **authoring**, it now saves **each job, term,
sitemap node, rule, story, scenario, wording and ERD row by its own `slice.py` call, as soon as that line
is written**, and the preview fills in place as the lines land. Nothing here changes what the registry is
or when anything is rendered: rule 2 is untouched, because the preview renders **in memory** (the same
generator, ~0 model tokens), never to disk, and a save is a registry write like any other.

**The cost, stated.** A line per tool call is about **2.5 s a line** (measured: median 2.5 s per call). A
list of 12 rows is half a minute of wall clock where one write took a few seconds. That is the price of a
page that fills while the work happens; a command that has nothing to show (a point fix to `/pb:build`) does
not pay it, and **a write of several lines in one call is still correct** — it just does not stream. Do not
split a list into lines to be tidy; split it because someone is watching the preview.

**The rule.**
1. **Start the preview before the first line.** `/pb:init` runs `serve.py registry.json --ensure` right
   after the first answer and seeds the registry at that point, so the first line already has somewhere to land.
2. **One line, one call.** `slice.py set <kind> <list>.<id> <patch>` for a line with an id (a job, a term, a
   sitemap node, a rule, a story); `slice.py append <kind> <list> <patch>` for a line without one (a wording
   with a `key`, an `erd.table` row, a story's `scenarios`). `append --key <field>` makes saving the same line
   twice a merge. A missing list is created (`--create-list` on `set`, automatic on `append`).
3. **Unapproved work is a draft.** Whatever waits behind a gate (**G-JTBD**, **G-IA**, **G-DIRECTION**, the
   *propose, human approves* gate of a vault) is saved with `--draft`: it goes to `.preview/drafts.json`
   under the registry's lock, **never to `registry.json`**, and the preview shows it with a Draft chip.
   When the gate is answered, write the approved lines **for real** (one call each) and run
   `slice.py drafts --clear`. A rejected draft is cleared the same way; nothing was ever in the registry.
   The `/pb:clarify` rule stands: jobs enter `ia.jobs[]` only after G-JTBD.
4. **The first call of a list says it is populated.** A tab with a populated flag (`flow`, `erd`) shows its
   rows from the first one, but set the flag with the first row anyway (`slice.py set erd populated` with `true`).
5. **Do not render, do not reload, do not poll.** The page takes `registry.json` and the drafts in place
   (`GET /__pb_data`); a body, the shell, the runtime or a stylesheet still reloads it, keeping the reader's
   tab, segment and scroll. Nothing a command does needs to ask the page to refresh.

**What the page does with it** (`serve.py`, `prototype.html`; `pb/commands/preview.md`).
- A change to `registry.json` or `.preview/drafts.json` is the SSE message `update`; anything compiled into
  the page is `reload`. The prototype shell paints `update` in place — the open tab, its scroll, its open
  rows and filters — and gives a newly arrived row a short arrival animation (none under
  `prefers-reduced-motion`). **A running Prototype session is never reset by it**: a change to `screens`,
  `components` or `tokens` while screens are running is a real reload, as before, and only that.
- A tab other than the one you are on that gets new content carries a **blue dot** until you open it. The
  page never changes tab by itself.
- **Before any screen**, the Prototype tab is an undesigned outline in the device frame, built by code from
  the registry and the drafts (name, objective, planned screens, their jobs, then paths and sample rows),
  and the **activity strip** under the bar (v2.7; on every project, while a session is live) says what Claude is
  doing from the hook: *Thinking* · *Writing · <step> · N saved* · *Your turn* (the gate it stopped at and what to
  approve, e.g. *G-JTBD — approve 4 jobs and 3 terms*; else the drafts to approve, or how long the turn took). A gated
  command names its gate with `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/activity.py" --gate <G-ID> "<ask>"` as the last
  tool call before its STOP message: it adds `gate: {id, ask, at}` to `.preview/activity.json` (never creating
  `.preview/`; a bad id or an empty ask writes nothing), `PostToolUse` and `Stop` keep it, `UserPromptSubmit` drops
  it. Stop does not fire on Esc, so *working* is believed for 90 s after the hook last wrote, then the strip
  reads *Waiting*. Before the first screen the strip's step name is the button of the **steps menu** — Brief ·
  Design system · Jobs and glossary · Structure · Flows and test cases · Wording · Data · First screen, each a jump,
  their counts from the registry and the drafts only; the menu is gone once `screens` is non-empty. The bar itself
  carries no progress item (it did until v2.7), and nothing of this appears on a view-only page.
- The site map of the Information Architecture tab draws `ia.sitemap[]` (`{ id, name, depth, parent }`) one
  node at a time, with a loading node shaped like the next one while the step is working, until the hub has a
  render body and `promote` has run: then the derived map takes over, as it always did.

## Schema compatibility

Write-path commands (`/pb:build`, `/pb:plan`, `/pb:pull-ds`, `/pb:handoff`, `/pb:init --import`) apply
this check before patching `registry.json`:

1. Read `meta.schemaVersion` from `registry.json` (absent → treat as schema 2).
2. Read `CURRENT_SCHEMA` from `migrations/manifest.py` in the plugin (currently **14** — 8 = W3C DTCG tokens, 9 = required atomic `level` / component-first, 10 = `anatomy`/`spec`/`usage`/`uiLogic` externalized to `spec/<kind>/<id>.json` sidecars via `specSrc`, 11 = the logic contract via `logicSrc` + the `ia` slice + `registry.runtime[]`, 12 = `meta.tradeoffs[]` collapsed into `ia.rules[]` as decision-carrying rules, 13 = spec sidecars in the Specs-plugin shape — `anatomy`/`layout`/`elements`/`shape`/`measured`, measured by `tools/spec_measure.py`; migration `0011`, 14 = a non-empty `meta.others` that no code reads moved out to `memory/others.md`; migration `0012`, which leaves a field that code reads in place and names the files).
3. If `schemaVersion < CURRENT_SCHEMA`: print a one-line banner —
   `⚠ Schema gap (v<from> → v<to>): <pending version update's describe() text>. Run /pb:update-version.`
4. Proceed — **unless** the current write touches a slice a pending version update changes,
   in which case **stop** and print: `Blocked: run /pb:update-version --apply first, then retry.`

Write-path commands reference this section rather than re-stating it.
Read-only commands (`/pb:test --drift`, `/pb:preview`) and exits do **not** carry this check.

## Rich text

Prose a person reads on a page (the Project Summary's `meta.overview.objectives`, principle bodies and
`meta.userInsights.*`, an IA job's `gap` note, a component's design notes in `purpose`) is rendered by
`pbRichText(str)` in `runtime.js` (both shells). It **escapes first**, then reads a small set of marks, so an
author (or `/pb:clarify`) can give a long text a hierarchy without markup of their own:

| Mark | Renders as |
|---|---|
| `**bold**` | strong |
| `*em*` or `_em_` | emphasis |
| `==the one thing to remember==` | a highlight (`.pb-hl`) |
| `{+an improvement+}` | positive, in the pass colour (`.pb-pos`) |
| `{-a problem or risk-}` | negative, in the fail colour (`.pb-neg`) |
| `` `code` `` | code, and opaque to every other mark |
| a line starting `·` `•` `▪` `- ` `– ` or `* ` | a bullet list |
| a line starting `1.` or `1)` | a numbered list (a different start number is kept) |
| a blank line / a single newline | a paragraph / a line break |
| a number with `%`, a currency or a unit, or a grouped number (`11,042`) | **bold**, automatically (`.pb-num`; `numbers:false` turns it off) |

An unbalanced mark stays literal; `{inline:true}` returns the marks only, with no blocks. The colours are the
tool's `--pb-pass` / `--pb-fail` tokens, so they follow the theme. The marks are authored, never inferred: the
writer agents add them under the limits in `/pb:clarify`.

## The demo model

Roles, permissions, people, entry points and data seeds for a prototype. All of it is optional: a project
that declares none behaves as before, and a project's own role or account module keeps working beside it.
**It is demo behaviour, not access control.** It runs in the browser, and `?role=admin` shows anyone that
role. A hand-off says so, and the real permissions belong on the server.

### Registry (`meta`, additive, no schema change)

```json
"permissions": {
  "levels": ["none", "view", "request", "approve", "apply"],
  "matrix": { "<role id>": { "<capability>": "<level>" } }
},
"personas": [ { "id": "reviewer-a", "name": "Reviewer A", "role": "<role id>", "scope": { } } ],
"demo": {
  "seeds": [ "empty", { "id": "two-open", "name": "Two open requests" } ],
  "entries": [
    { "id": "first-run", "name": "First run, whole flow", "screen": "<screen id>",
      "role": "<role id>", "persona": "<persona id>", "seed": "<seed id>", "default": true, "note": "" }
  ]
}
```

- `levels` runs lowest to highest; the first means no access. A capability a role's row doesn't name, or a
  level the matrix doesn't declare, counts as the first level. `scope` is plain data for the project's own
  rules; pb never reads it.
- In an entry only `id`, `name` and `screen` are required. At most one entry has `default: true`; with
  entries but no default, the first entry is the default.
- A persona with no `role` fits any role.

### What a body or a project module can read (`window`)

| Call | Returns | With nothing declared, or on the design-system site |
|---|---|---|
| `pbRole()` | the active role id | `null` |
| `pbPersona()` | the active persona object | `null` |
| `pbCan(capability, minLevel)` | `true` when the active role's level is at least `minLevel`; omitted means the lowest level above the first | `true` |
| `pbSeed()` | the active seed id | `null` |
| `pbEntry()` | the active entry object | `null` |
| `pbCtx()` | the `data-ctx` of the click that opened this screen | `null` |
| `pbBack()` | goes back; a no-op with no history | no-op |
| `pbApplyEntry(id)` · `pbSetPersona(id)` · `pbSetSeed(id)` | set it; each returns `true` or `false` | `false` |
| `pbSandboxRow({id, label, options, get, set})` | adds a select row to Sandbox → Conditions; callable while a runtime module loads; `options` is `[{value, label}]` or a function returning it; `set(value)` is followed by a repaint; a row with the same id replaces the earlier one | no-op |

`pbCan` is `true` for an `isAdmin` role before any other check (an unknown `minLevel` included) and when
`meta.roles` is absent. Otherwise an unknown `minLevel` is `false`, and `pbCan('x', '<first level>')` is
`true` for everyone. Names beginning `pb` are the tool's; a project module shouldn't define its own.
A body reads these; it doesn't write its own role module.

Setting a person from another role (`pbSetPersona(id)`, `?persona=`) switches to that person's role, and
when `?role=` and `?persona=` disagree the persona wins.

**Events** fire on `window` **before** the re-render, so a body sees the new value on the first frame, and
only on a real change: `pb:rolechange` `{role}` and `pb:seedchange` `{seed}` carry ids; `pb:personachange`
`{persona}` and `pb:entrychange` `{entry}` carry the objects the getters return. `pb:reset` always fires,
with `{entry: null}` when no entries are declared.

### Markup

- **`data-can="<capability>[:<level>]"`** gates a control by capability, with `data-can-mode="hide"`
  (default) or `"disable"`, which also sets `disabled`, `aria-disabled` and a `title` naming what's missing.
  It re-evaluates on every render, in every Compare frame. The value splits only when the tail is a declared
  level. `data-roles` keeps its meaning and can sit beside it.
- **`data-ctx="<subject>"`** on the `data-nav` element says what was tapped (it is read nowhere else). Going
  back restores the subject of the screen you return to; a `data-nav` without `data-ctx` clears it.
- **`data-back`** is a real back. `data-back="<screen id>"` names where to go when there is no history.
- **`data-nav-reset`** on a screen's root empties the history as that screen is left, by any departure
  including back: you can't go back through it. The first screen after it falls through to its own
  `data-back` value.

### Sandbox → Conditions

In order: **Start from** (entries) · Device · Chrome · Compare · Structure tree · Role · **Person** (only
that role's personas) · **Data** (seeds) · project rows from `pbSandboxRow` · **This role can** (read-only,
capability and level). A row with nothing to show isn't drawn. In Logic, the Permissions table shows in the
Rules view, and a project with a matrix and no rules lands on Rules.

- **Start:** `?entry=` wins, then the default entry, then the older rule (`screens[0]`,
  `meta.defaultRole`). `?role=` and `?persona=` apply on top, and `?role=` works with no demo model
  declared. An unknown value is ignored with a console warning, never an error.
- **Seeds:** an entry with no seed gets the first declared seed. With seeds but no entries, Reset goes back
  to the first seed. Applying an entry and Reset always call `pbScenarioSwitch(seed)`, so a project can
  re-seed.
- **Picking an entry** applies its screen, role, person and seed, and clears history and subject.
- **Reset** (the button or R) returns to the entry as declared, not to a `?role=` override. With no entries
  it behaves exactly as before.
- **Changing role** keeps the person if they belong to the new role, otherwise picks that role's first
  person, or none. An entry whose role can't see its screen falls through to the permitted-screen rule.

### Checks

- `lint_registry.py`: **`R-ENTRY`** (unknown screen, role, persona or seed; more than one default; an entry
  role the screen doesn't allow; duplicate ids) and **`R-PERM`** (a matrix naming an undeclared role or
  level; a persona naming an undeclared role; a `data-can` or `pbCan()` capability no matrix row names).
  WARN, ERROR under `--strict`.
- `/pb:test` roles lane (`test_run.py --roles`): **`T-PERM`** (every role × capability against the matrix
  through `pbCan`, every `data-can` control on every screen) and **`T-ENTRY`** (every entry opened with no
  console error). Scenarios may carry `test.entry` and `test.persona`, applied before `test.start`.

### What must not change

Real project modules call these, so they keep their names and meaning: `renderPrototype`,
`setProtoScreen(id, fromBack)`, `setProtoRole`, `pbResetSandbox`, `pbSetStep`, `pbPreserve`,
`pbResolveDefaultRole`, `pbApplyRoleGating`, `pbNavAllowed`, `pbProtoSubmit`, `pbScenarioSwitch`, `PB_DATA`,
`PB_REGISTRY`, `state.protoScreenId`, `state.activeRole`, `state.protoHistory` (an array of screen ids),
`state.metaView`, and the `proto-frame`, `proto-screen`, `proto-pair` hooks.

Data scope rules and approval routing stay project logic; personas carry `scope` so those rules have what
they need.

## Research evidence

`/pb:research` validates what a project is unsure about with real people and keeps what comes back as
evidence a later reader can check. Six methods: survey and interview (asked in a tool the user already has),
and usability test, tree test, card sort and first-click test (run in a browser on the prototype, as
**sessions**). The registry's optional `research` slice holds the studies (the plan, hypotheses, the
instrument, the participant tracker and logistics checklist, the evidence index, the tally or the analysis,
the observations, themes and issues, the findings); the raw files live on disk. Absent means an empty
state, not a schema bump. The method is in the `ref-research` skill; these are the rules that do not move.

- **Nothing is hosted online.** No survey page, no panel, no public or LAN link. A survey or interview is
  fielded elsewhere and its export comes back. A session method runs **on this machine** (the `/pb:preview`
  server, moderated, with an optional observer window) or **from one kit file** the participant opens on
  their own disk and sends results back from (unmoderated). The session pages and uploads answer this
  machine only (loopback peer and Host), whatever `--host` or `--allow-host` says; the participant's page
  never live-reloads. Screen capture needs a secure page, which `127.0.0.1` and a local file are and a
  plain-http LAN address is not, so pb offers no LAN link.
- **Evidence is immutable.** A raw file is copied to `memory/research/<id>/evidence/`, hashed (sha256) and
  made read-only. Nothing edits it. A mistake is fixed by dropping the evidence and importing a corrected
  one; a drop deletes the file and keeps its row, struck out, with the hash and the reason. A session and its
  recording are two evidence files, linked: **dropping the session drops its recording too.**
- **A recording is participant data, and consent comes first.** The participant page asks for consent to
  take part (required), and only if the instrument asks, a **separate opt-in** to record the screen and
  voice. A recording is stored only for a session whose participant opted in, read-only and hashed like any
  evidence. It is left out of a mode 1 hand-off unless `--with-recordings` is given (see Hand-off). The recorder captures events (screens, clicks, dead and rage clicks, validation errors, task
  outcomes) and field input as **length only, never the value**.
- **A pilot is never evidence.** A rehearsal is stored under `memory/research/<id>/pilot/`, left out of the
  tally, the analysis, the findings and the report, whatever it showed.
- **A participant never sees the study.** The session page and the kit carry the prototype, the tasks, the
  tree or the cards, and the consent text. They never carry the study's title, question, hypotheses,
  thresholds, success criteria, answer keys, the `research` slice or the insights.
- **Numbers by the tool, quotes verified verbatim.** Every count, mean, percentage, rate, time and score
  comes from `research.py tally` (survey) or `research.py analyze` (sessions: success with an adjusted-Wald
  interval, time on task as a geometric mean with an interval, lostness, clicks, errors, SEQ, SUS with its
  grade, and the tree, sort and click results); the model computes none. An issue's participants,
  frequency and priority are the tool's too, and a typed one is refused. The model proposes an issue's
  severity (Nielsen, 0 to 4) and the user approves it at G-INSIGHT. Every quote must appear verbatim in the
  cited evidence file, every observation cites a session event, a time or a verbatim quote, and `verify`
  fails a finding whose quote or number does not match, recomputing the analysis fresh from the evidence. A
  failing `verify` is fixed, never presented around.
- **The report.** `report` is refused unless `verify` is clean. It writes `report.md` and a self-contained,
  printable `report.html` under `memory/research/<id>/report/`, served at `/research/<id>/report`, with
  participants by pseudonym only. It carries a Draft banner until G-INSIGHT, and `refill --approved`
  regenerates it without the banner.
- **Two gates, both blocking.** **▛ G-STUDY ▟** approves the plan, the instrument and the hypotheses with
  their thresholds before anyone is asked; **▛ G-INSIGHT ▟** approves the verdicts, the issue severities,
  the report and the exact refill text before `meta.userInsights` changes. Each presents the artifact, not a
  summary; silence is not approval. Editing an approved instrument, or the plan's objectives, research
  questions, decision, method rationale or participants, withdraws the first (the plan's logistics keys do
  not); and a change after the second re-opens it.
- **Every run starts by asking what it is for.** `/pb:research` asks, at every run and before anything
  else, whether the user wants just the questions and the setup (scope `instrument`, which ends after
  G-STUDY and refuses `import`) or questions plus results (scope `collect`), and what survey tool, panel or
  participant list they have. The model never picks the scope for them.
- **The instrument is reviewed by an agent that has not seen the study.** Before G-STUDY a fresh `pb-tester`
  gets only `bias-review.md` (the questions, as yes/no items), never the hypotheses; its rows are stored by
  `research.py review`. The authoring context cannot overturn a `no`; `approve` refuses with no current
  review unless the user gives `--skip-review "<reason>"`, and a `no` or `blocked` row stands only on the
  user's `--accept-review "<why>"`. The G-STUDY gate shows every such row.
- **Thresholds are fixed before data.** `supportedIf` and `refutedIf` are written at G-STUDY and never
  moved after seeing results. Inconclusive is an honest verdict.
- **The model never simulates respondents or sessions.** No synthetic users, no invented answers, no
  placeholder evidence, no session run by the model and stored, labelled or not. An instrument is fielded
  with real people, or the study is not run. (Test fixtures in `tests/` and `fixtures/` are the only
  synthetic data, and are marked as such.)
- **Consent and pseudonyms.** A file is imported only with consent recorded as `yes` or `unknown`
  (`no` is refused, and `unknown` is carried as a warning to G-INSIGHT); a session records the
  participant's own consent. Participants are `P01`, `P02`; no real names, emails or phone numbers are asked
  for or stored (a tracker note that looks like one is refused), and PII columns are dropped on import. A
  participant who withdraws is dropped, and no finding may rest on them.
- **A verdict is a proposal.** A finding that changes a job, a rule or the structure is routed
  (`/pb:clarify`, `/pb:clarify` § 2, `/pb:explore`), never applied by `/pb:research`. The only automatic
  write to the project's prose is the approved `refill` into `meta.userInsights`, with a citation and a
  backup.
- **Hand-off.** Mode 1 (everything) carries `memory/research/` in the bundle, since the recipient keeps
  building, through `research.py bundle`, never a hand copy. **Screen and voice recordings stay out by
  default**; `/pb:handoff --with-recordings` carries them, and only when the recipient is covered by the
  participants' consent (the model asks first). The bundle's registry copy marks each left-out recording
  row with `withheld: {at, reason}`, and `memory/research/HANDOFF.md` lists what was left out (path, bytes,
  sha256) and how to put one back. The recipient keeps the row and its sha256: `verify` warns `W-WITHHELD`
  (never an error), the report adds a limitation line, and the replay plays the event log without video.
  Session event files (clicks, screens, no typed text) and transcripts still travel. Modes 3 (Figma) and 4
  (tickets) carry none, and never raw evidence: participants' words and faces do not leave the team that
  has their consent. (Mode 2, engineering, was retired in v3.0.0.)
- **`/pb:clean` never prunes it.** Evidence is the one thing in `memory/` that exists to outlive the
  tool's housekeeping; removing it is a human act, on a named study.
