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
   `slice.py get <kind> <id>`; write it with `slice.py set <kind> <id>` — it takes the registry lock.
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
  `.proto-screen`, the design system's demo stage and variant cells, the React scaffold's root. A
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
`<style id="pb-product-css">` in both sites and in the React scaffold. A sheet styles its own root class,
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
- **NEVER start `serve.py` with `&` or `nohup`, and never with `--idle-exit 0`** — `serve.py registry.json --ensure`
  starts or finds it. `explore.py link` does the same when it needs one.
- **NEVER `kill` or `pkill` a preview, or hunt for it with `lsof`** — `serve.py --status` finds it and
  `serve.py --stop` stops it; it also exits by itself after 8 idle hours.
- **NEVER write `registry.json` by hand** (`json.dump`, `open(…, 'w')`, a redirect) — `slice.py set`.

**Hooks put the key rules in front of the model.** The plugin's `hooks/` folder runs three small scripts
in any pb project (a folder with `registry.json` and a `render/` folder or `memory/constitution.md`, in the
working directory or under `.prototype/`): `session_rules.py` prints a short digest of these rules at session
start, and `bash_advice.py` adds one line of advice before a shell command that matches a rule above. They
only advise — never block, never decide a permission — and print nothing outside a pb project.

## Schema compatibility

Write-path commands (`/pb:build`, `/pb:plan`, `/pb:pull-ds`, `/pb:handoff`, `/pb:init --import`) apply
this check before patching `registry.json`:

1. Read `meta.schemaVersion` from `registry.json` (absent → treat as schema 2).
2. Read `CURRENT_SCHEMA` from `migrations/manifest.py` in the plugin (currently **13** — 8 = W3C DTCG tokens, 9 = required atomic `level` / component-first, 10 = `anatomy`/`spec`/`usage`/`uiLogic` externalized to `spec/<kind>/<id>.json` sidecars via `specSrc`, 11 = the logic contract via `logicSrc` + the `ia` slice + `registry.runtime[]`, 12 = `meta.tradeoffs[]` collapsed into `ia.rules[]` as decision-carrying rules, 13 = spec sidecars in the Specs-plugin shape — `anatomy`/`layout`/`elements`/`shape`/`measured`, measured by `tools/spec_measure.py`; migration `0011`).
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
