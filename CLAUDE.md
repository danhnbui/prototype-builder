# Product Builder v2.3.0 — router (read first)

Standalone, CLAUDE.md-native prototype builder. **No SpecKit** — no `extension.yml`,
`preset.yml`, or `after_*` hooks. State lives in `registry.json`; commands are native
`.claude/commands/pb:*.md` files. Full data contracts + render-function inventory live in
the playbook, [prototype-builder.md](prototype-builder.md) (authored in Phase 2).

## Commands (`/pb:*`)

| Command | Does | Lands |
|---|---|---|
| `/pb:init` | Scaffold: PRD intake (Q&A or file), set Stack + DS locks, seed `registry.json` + `memory/`; `--import <bundle>`; **`--figma <frame>`** (resolve a Figma frame → screen, gaps → `gaps.md`, `meta.entry=figma`); **adopt-in-place** under `.prototype/` inside an existing repo | P4 |
| `/pb:pull-ds` | Clone the design system (fallback ladder: DS MCP → Figma link → code library → common) → registry tokens + `design-system/<name>/` reference + `.source.json` drift snapshot; records `meta.dsSource` + `meta.platform` | P4 |
| `/pb:specify` | Produce the spec / PRD (native) | P4 |
| `/pb:clarify` | User Insights → Project Summary; **the jobs each role needs done → `ia.jobs[]`**, approved at **▛ G-JTBD ▟**; then **the IA** — N genuinely different groupings of those jobs, written by the coordinator, scored on the compare page (`explore.py --ia`, `/explore/<ia-id>`) and one promoted at **▛ G-IA ▟** (`ia.jobs[].screens[]`, `ia.layers[]` purposes, `meta.navHub`; `--ia-options N`, `--skip-ia`; skill `ref-ia`) — both in UX Design → Information Architecture; each contested UI decision → **one `ia.rules[]` rule carrying the `decision{}` it was made by** (UX Design → Logic → Rules, D-33 — there is no separate trade-off record); append each to `decisions.md` | P4 |
| `/pb:plan` | Implementation plan **+** per-tab task breakdown (acceptance · skill · **agent · deps · slice**) **+** **consumes the IA `/pb:clarify` chose** (a task per planned screen and for an unbuilt hub; no chosen IA → it stops and names `/pb:clarify`; `--ia <job-id> --into <screen-id>` places one late job, never regroups) **+** first authoring of the `flow` and `erd` slices (`--flow` / `--data` / `--mock`). Routine changes need none of it — `/pb:build` reconciles both automatically | P4 |
| `/pb:orchestrate` | Dispatch `memory/tasks.md` to the agent roster in dependency **waves** — serial registry writes, render once per wave, `acceptance`-gated | P4 |
| `/pb:build` | The cheap loop: targeted `registry.json` patches, trio-gated, **no per-tweak render**. §3a is the DS-first check on every new/changed component (reuse → variant → local + the naming contract) | P3 |
| `/pb:preview` | Live preview dev server: watch `registry.json` → deterministic render → live-reload (**it stops itself after 30 idle minutes**; `serve.py --status` / `--stop`; see *pb bounds its own footprint*). **One server, two routes** — the prototype at `/` and the design-system workbench at `/design-system` (§2b: live demo with Anatomy · Spec layers, variants & spec, anatomy, Push-to-Figma, tokens) — plus `POST /api/meta` (the Project settings save) and `/explore/<id>` while a `/pb:explore` is open (§2c) | P3 |
| `/pb:test` | **Check everything.** No flag = scenarios · roles · server · security · constitution drift · ranked health · shell coherence · DS drift, one verdict; the three browser modes run as one `test_run.py --all` against the running preview. Writes a **yes/no test plan** first (`memory/test-plans/`, one item per test case, never an open question), delegates it to **sonnet `pb-tester` subagents** that never saw the design being built, then reconciles their rows against the plan. A mode flag narrows it (`--drift` is the old `/pb:check-drift`) | P3 |
| `/pb:report` | **Retrospective for the pb maintainer.** `tools/report.py` turns the project's history — `decisions*.md`, hand-written `memory/` files, backups, explore manifests, render-body comments, render timings, lint and test counts, and (opt-in, `--sessions`) the session transcripts as counts and sequences only — into one facts file; the model appends ranked proposals for the next pb release. `--since <date>` windows it. Read-only on the project: writes only `memory/reports/pb-report-<date>.md` | v2.1 |
| `/pb:explore` | **Two modes.** An **id** → a one-screen direction approved at **G-DIRECTION** → one execution plan per bet → N `pb-explorer` sub-agents (sonnet, xhigh) build them → **one compare-and-rate page at `/explore/<id>` on the `/pb:preview` server** → a scoring gate → keep one (`tools/explore.py`; registry untouched). **Every stop that shows options ends with that page's browser URL**, printed and checked by `explore.py link <id>` (it finds or starts the server); a file path or editor link never stands in for it. A subject that is no registry body (the tool's own chrome, a mockup) is a page round, `init --pages`, on the same page. A **goal sentence** → the gated discovery pipeline (below), stopping at **G-JTBD**, **G-DIRECTION** and **G-DESIGN**. `explore.py --ia` runs `/pb:clarify`'s IA round on the same engine. `explore.py list` shows each open round's age and flags it `STALE` past 3 days; `promote` / `reject` name the rounds still open | P3 |
| `/pb:handoff` | **The one hand-off command.** Asks who is receiving it: **1** everything incl. a vendored Product Builder (recipient keeps building) · **2** engineering — `prototype.html` + `design-system.html` + `logic.md` + `rules.md` + `constitution.md` · **3** Figma, lowered deterministically then written through the MCP (falls back to the DS Bridge plugin). Mode 2 tiers: `host` (a runnable Vite/Next build serving the file) · `scaffold` (React+Tailwind). One command; no sub-commands | P6 |
| `/pb:update-version` | Versioned schema update: dry-run / `--apply` / `--rollback` / `--to <N>` | P6 |
| `/pb:clean` | **What the project has piled up, and pruning it on request.** `tools/clean.py` is a dry run by default — open explore rounds (with age, `STALE` past 3 days), closed rounds, `memory/backups/`, `.pb-backups/`, `.preview/server.log`, `.preview/shots/`, orphan `render/_candidates/` folders, the preview server. Bare `--apply` does only the always-safe set; **a backup or a closed round is deleted only by an explicit `--keep-backups N` / `--keep-closed N`**, never an open round, never a server (`serve.py --stop`) | v2.2 |

> **Retired — the files are gone, not stubbed.** AGENTS.md §2 requires an alias for a rename; these shipped without one, which is why **v2.0.0 is a major** (D-34). Users upgrading follow [docs/upgrade-to-2.0.md](docs/upgrade-to-2.0.md). `/pb:flow` + `/pb:data` → `/pb:plan --flow` / `--data` (and their older `sync-` aliases) · `/pb:check-drift` → `/pb:test --drift` · `/pb:handoff-close`, `/pb:handoff-dev`, `/pb:hand-off`, `/pb:build-figma-handoff` → `/pb:handoff` · `/pb:build-check-design-system` → `/pb:build` §3a · `/pb:preview-ds` → `/pb:preview` §2b · `/pb:validate` → `/pb:handoff --tier=host`. 24 commands became 12 at v2.0.0; `/pb:report` (v2.1) and `/pb:clean` (v2.2) make 14.

> **Skills are internal, not commands.** The 18 `pb/skills/*` set `user-invocable: false` — commands and agents load them; users never type them (the `think-clarify` skill is not a second `/pb:clarify`). The shell's `?` dialogs list commands only. `tests/skill_refs_lint.py` enforces both, and that every skill or `/pb:<cmd> --<flag>` a doc or shell names exists.

> Shipped as a Claude Code **plugin** (`pb@product-builder`, defined in `./.claude-plugin/marketplace.json` + `./pb/`) — commands invoke as `/pb:*`. After install, **restart Claude Code** to load them. (G1 decision: plugin ✓)

## Agent roster + sandbox (v1.5)

- **Agents** (`pb/agents/*.md`, installed to `.claude/agents/` via `tools/agents_install.py`): `pb-clarifier`, `pb-planner`, `pb-builder`, `pb-design-system`, `pb-flow`, `pb-data`, `pb-tester`, `pb-reviewer`, and `pb-explorer` — the ninth, dispatched only by `/pb:explore` (one per execution plan, `model: sonnet`, `effort: xhigh`), never routed by `/pb:orchestrate`. **`pb-explorer` is not installed by the plugin alone: run `tools/agents_install.py` and restart the Claude Code session before `/pb:explore` can dispatch it.** `/pb:orchestrate` routes each task to its fitting agent by `slice`; agents **return slice patches**, the coordinator applies them **serially** and renders **once per wave**; `pb-tester` + `pb-reviewer` are the `acceptance` gate.
- **Sandbox** (`/pb:test` → `tools/test_run.py`, Playwright — the only pip dep, isolated to this path like Node/npm at `/pb:handoff --tier=host`; degrades if absent; every browser it opens goes through `tools/browser.py`, see *pb bounds its own footprint*): drives the `data-*` runtime to verify scenario `test{}` blocks, per-role gating, and server reachability; `tools/security_scan.py` (stdlib) scans for secrets/PII. Results write `flow.stories[].scenarios[].lastResult` (additive) → the UX-tab ✓/✗/○/☐ glyphs.
- **Independent grading (v2.0.0).** A test run is **planned, then delegated**. `/pb:test` §2a writes
  `memory/test-plans/<stamp>.md` — one item per test case, each a binary question whose `yes` means the
  check held, and **never** an open question (no "should", nothing answerable *it depends*; a check that
  can't be phrased that way produces no item). §2b hands the items to `pb-tester` subagents on **sonnet**,
  one per lane, with the plan path and nothing else — no spec, no plan, no decisions log, no prior
  `lastResult`, no framing from the authoring conversation. They return `<id> · yes|no|blocked · evidence`
  rows and nothing else; §11 reconciles every id back against the plan, cannot drop one, and cannot
  overturn a `no` (it dispatches a fresh agent and shows both). `--no-delegate` self-grades and says so.
  The reason: the context that authored a design reads its own intent and scores the intent.
- **Roles** (all additive/optional): `meta.roles[]` + `meta.defaultRole` + `screens[].roles[]` + element `data-roles` gate the Prototype tab; the role switcher (Sandbox → Conditions) and **Reset** (the Sandbox footer, or R) stay available (kept visible to viewers even in a `--people` hand-off — only authoring controls hide); an `isAdmin` role bypasses gating.

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

Full rules: `AGENTS.md` §8–§9. Executable form: `pb/commands/explore.md` Mode B. This is the canonical
text — commands reference this section rather than re-stating it.

## The three load-bearing rules (token levers — ship together)

1. **State in `registry.json`.** The loop reads/edits only the touched slice. `prototype.html`
   is **never** the source of truth and is **never** hand-edited.
2. **Batched, deterministic render.** A generator regenerates `prototype.html` from `registry.json`
   ONLY on `/pb:build --render` and automatically at `/pb:handoff` — **never** per tweak,
   and **never** by the model hand-emitting HTML (that is ~2–3× *worse* — measured at G0.5).
   *(`/pb:preview` may render on every change without breaking this: it's the **same generator**
   rendering **in memory** at ~0 model tokens — never the model, never written to disk unless `--write`.)*
3. **Gate-skip on non-trio tweaks.** The drift / Stack / DS gate runs only when a change touches
   the **trio** — a screen, a component, or logic. Pure cosmetic tweaks skip it.

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

This is the canonical text. `/pb:build`, `/pb:plan` and `/pb:orchestrate`
reference this section rather than re-stating it.

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
  `pb/template/product.css` adds `r-compact` · `r-medium-up` · `r-expanded-up` · `r-below-expanded` ·
  `r-cols` · `r-measure` for swaps that need no sheet. Contract: `prototype-builder.md` → *Responsive styles*.
- **Enforced** by `lint_registry.py`: `R-STYLE-MEDIA` (a size `@media`), `R-STYLE-SCOPE`, `R-HEX`/`R-PX`
  in sheets, `R-STYLESRC` (missing file), and `R-RESPONSIVE` — `meta.responsive` `false` across several
  size classes, or `true` with a screen nothing in which adapts (`null` is `/pb:build`'s question, never a
  lint finding — an older project's CI stays green).
- **Looked at.** `think-layout` §5 screenshots every listed size; the expanded frame must not be the
  compact layout stretched.

This is the canonical text. `/pb:init`, `/pb:build`, `think-layout` and `design-component-build`
reference this section rather than re-stating it.

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
  ```
  Defaults: 1440x900 and 390x844. `--selector`, `--click`, `--wait-for`, `--eval` and `--full-page` cover
  what a throwaway script was written for. Exit `3` = cannot run (no Playwright) — *blocked*, not passed.
- **A preview server stops itself.** After 30 minutes with no browser tab open and no request it exits
  and drops `.preview/server.json` (`--idle-exit MINUTES`, `0` = never; `PB_PREVIEW_IDLE_MIN`). It is
  started by `/pb:preview` or `explore.py link`, inspected with `serve.py --status`, and stopped with
  `serve.py --stop`.
- **Growth is visible and prunable.** The health report (`lint_registry.py --report`, part of `/pb:test`)
  has a `resources` block that ranks backups, open and closed explore rounds, `server.log` and an
  oversized registry key; `/pb:clean` shows the same piles and prunes them. **Nothing is deleted without an
  explicit keep flag** — `/pb:clean --apply --keep-backups N` / `--keep-closed N` are the only way pb ever
  deletes a backup or a closed round.

The three rules agents follow:

- **NEVER hand-write a Playwright script to look at a prototype** — use `shot.py`.
- **NEVER start `serve.py` with `&` or `nohup`** — `explore.py link` (or `/pb:preview`) starts it.
- **NEVER `kill` a preview** — `serve.py --stop`; it also exits by itself after 30 idle minutes.

This is the canonical text. Commands, agents and skills reference this section rather than re-stating it.

## One registry → two sites, one preview server

The registry is the single source of truth, projected into **two** deterministic sites (both built by
`/pb:build --render`, both served live by the one `/pb:preview` server, both ~0 model tokens — the token
lever): the **prototype** (`prototype.html`, `/` — flows/screens, **4 tabs**) and the **design system**
(`design-system.html`, `/design-system` — the component workbench: a live demo with
Anatomy · Spec layers, variants & spec, anatomy, push-to-figma, tokens). Neither HTML file is ever hand-edited (they're derived); a component edit
re-renders both. `/pb:preview` keeps **one** canonical `.claude/launch.json` entry per project
(`pb-preview · <folder>`) via `pb/tools/preview_register.py` — **one server, two routes**; entries it
doesn't own are left alone.

## Tab render behaviors (the prototype shell, `pb/template/prototype.html` — 4 tabs)

**Unified page chrome (v1.2).** Every tab shares one layout: a `pb-page-header` (title + a `?`
**info-dialog** explaining the tab's commands/skills + an optional CTA, shown only when the tab has data),
over a `pb-content` shell — `--full` (single column, Project Summary only) or `--split` (left main · right
aside, 400–600px). When a slice is unpopulated the tab renders **only** the header + an **empty-state**
card that owns the CTA — no dead controls. (Replaces the old `meta-tag`/`meta-sub` per-tab headers.)

- **Prototype** — interactive, **no** screen-switcher. Each frame's screen is a `pb-screen` container, so
  a project's container queries answer the frame, not the window (see *Responsive across devices*). A declarative `data-*` runtime drives a real flow:
  `data-nav="<id>"` navigates; `data-action="toggle-password"`; `data-action="submit"` validates the form
  (`data-required` · `data-validate="email"` · `data-minlength`) then `data-go` / `data-toast` /
  `data-redirect`+`data-redirect-ms`; **`data-machine`/`data-step`** drives a wizard (`data-step-pane`
  shows and hides with the state, `data-step-go` advances it, `pbSetStep()` for a transition a click
  cannot express); **`data-preserve`** marks what survives a re-render (`pbPreserve(fn)` captures,
  re-renders, restores, then fires `input`+`change` once everything is back). The preview fills the tab
  and **every control lives in the Sandbox inspector** — there is no page header here, and
  no caption or footer under the frames (the devices are named in the Sandbox; each frame keeps an
  accessible name). **Phone and tablet frames are scaled to fit whole**, with a 32px inset (24px under 900px tall),
  recomputed on resize and when the inspector is pinned; laptop and monitor are unchanged, and Compare keeps its
  one shared transform. **R resets the session** — never while typing in a field, never with Cmd/Ctrl held
  (Cmd+R is reload), never on the other tabs, and not on key-repeat.
  *Conditions (the Sandbox's first section):* a **Browser | App | None** chrome toggle (`meta.shell` default; browser = a Chrome window
  drawn at Chrome's own metrics and in Chrome's own neutrals — window controls, a tab with its notch, an
  omnibox that de-emphasises everything but the host — and on **mobile** a phone's browser instead: status
  bar + one address pill; on **tablet** the OS status bar over a tab strip and a toolbar, with none of a
  desktop window's furniture — no traffic lights, no extensions; app = a titlebar with window controls on
  desktop, a contrast-aware status bar on tablet/mobile; none = a flat screen with no chrome at all —
  tablet/mobile keep their device frame. A **status bar** is the device's, not the chrome mode's: every
  tablet and phone mode shows one, and the **Dynamic Island is drawn on the phone only**) · an
  icon-only device switcher over **4 fixed sizes** (monitor 1920×1080 · laptop 1280×832 · tablet 834×1112 ·
  mobile 429×926), default from `meta.device`, sizes not in `meta.devices` **disabled** · **Compare**, a
  mode switch that adds exactly **one** more device showing the same screen — each frame lays out at its
  **true CSS width** and the pair shares **one** transform, so the size ratio on screen is the real one.
  Two frames, **one session**: markup, field state and scroll all mirror across (scroll as a proportion,
  since the two widths lay the screen out at different heights), a click in the second frame is replayed
  on the first, and each secondary frame's radios get a form owner of their own — one document otherwise
  means one id space and **one radio group**, which silently emptied the frame whose radio lost ·
  a **Structure tree** panel — the product's **pages, by name**, indented by their depth in the derived nav
  graph (flat when a project has none), each one a jump; it pushes the preview aside and stays until you
  close it. ⌥-click in the preview is the tool for *what is this element*, and it answers from the DOM.
  *Sandbox — the inspector.* A 20rem panel on the right, closed by default, opened by the bar's **hourglass** or by
  **S** (under exactly R's guards: never while typing, never with Cmd/Ctrl held, not on key-repeat). **Esc closes it
  unless it is pinned**; the **pin** docks it and **pushes the stage** aside (closing a pinned inspector unpins it).
  Three flat sections: **Conditions** (device · chrome · Compare · Structure tree · role — the controls above) ·
  **Run** · **Explore**. **Run** is collapsible — **closed by default** — and grouped by story: each group and each scenario is a multi-open
  disclosure with a pass / fail / not-run tally, plus *Run all* and Collapse all. A scenario runs **in the page** — the
  stage moves to its start screen and each step ticks pass / fail / blocked in place. A scenario whose `test` is
  prose or a string is **listed but not runnable** (blocked: run `/pb:test`, the one place a verdict is recorded, and
  the only writer of `lastResult`). **Explore** is disabled, with its reason and `/pb:explore <id>`, until a round
  is open. **Reset session** sits in the footer, last, after everything it resets.
  *The bar.* The **project button** at the left (initials square + short name + chevron; initials only below 600px)
  opens a menu: **Project settings…** · theme · version. **Project settings** edits the project name, the
  **design-system name (required)**, the **Figma file (optional — a figma.com file/design link)** and the **theme**
  (System / Light / Dark, per viewer). A save goes through `POST /api/meta` on `/pb:preview` — loopback and
  same-origin only, written under the registry lock (see `pb/commands/preview.md`); over `file://` the dialog is
  **read-only** and hands out plain prompts to paste into Claude Code. **⌘K** (Ctrl+K) opens global search — rules,
  jobs, components, screens, test cases, content terms and commands — grouped, arrow keys, Enter jumps. The
  project button, settings dialog and ⌘K are `runtime.js`'s, shared with the design-system site.
- **Project Summary** — split: **left** = the `meta-subtab` sub-tabs (Overview · Insights) over a scrolling content column — and nothing else (D-33): a trade-off is a rule, so it lives on the rule in UX Design → Logic, and `meta.others` (no schema, no writer, no check) is retired with its tab; **right** = a **scroll-spy table of contents** (built from the content's headings) that highlights the section in view and navigates on click. One viewport, internal scroll. Prose is **rich text** (`pbRichText`; the marks are in `prototype-builder.md` → *Rich text*): a lead paragraph set a step larger, principles as a numbered list, a measured column. **The table of contents appears only with ≥ 3 headings** — below that the aside is dropped and the content takes the room.
- **UX Design** — **five segments**: Logic · Information Architecture · User Flow · Test Cases · **Content**. Content is the `content` slice — a **glossary** (`terms[]`: what a domain word means, what else the team says for it, and what it is deliberately never called) over a **wording deck** (`strings[]`: the canonical text for every action, status and message, grouped by `kind`). Both halves are hand-authored — nothing derives them — so the one check it runs is authored-vs-authored: a wording, **or a declared rule's state label**, that uses a word another term banned. A term may carry `rule: "<ia.rules id>"`, which links it to the Logic segment and back. Split layout for the other segments: **left** = the `flow.mermaid` canvas (multi-flow dropdown + legend, straight **orthogonal**
  connectors anchored at node side-centers, nodes recolored by shape and **Yes/No branches drawn green/red**),
  filling **one viewport** — no W×H controls; **right** = **User stories | Test cases** from `flow.stories[]`.
  Hovering a story **highlights the flow path it satisfies** (matched nodes + edges, rest dimmed).
  - **Logic** — one-line scan rows (pattern glyph · id · title · status · kind · a tiny preview such as "4 states" or
    "prose only") that are *disclosures*: **several open at once** (one shared disclosure primitive; nothing closes a
    sibling), under a filter bar (search · Status · Kind · **Pattern** — Flow · Tables · Values · Effects · Prose only —
    **Clear** right after the last chip, "N of M") with Expand all / Collapse all. A card is a **visual stack** in a fixed
    order (lifecycle statechart, then Flow, Tables, Values, Effects blocks); a rule with none says *prose only* and names
    what it looks like (`logic_shape.py`). Rule text, Decision, Open questions, History, Tests and Sources sit behind one
    **Details** button, which opens a right-side drawer. **One status rule** for row and card: "to resolve" counts assumptions.
  - **Information Architecture** — vertical: the site map on top, the job list under it, and **one filter bar**
    (search · Role · Priority · Screens · the quick chip *Not handled*) that filters the jobs and **dims** the
    non-matching map nodes together. Roles are `meta.roles` plus any a job cites (an undeclared one is marked).
  - **Test Cases** accept **both scenario shapes**: the authored `test{}` object, and a prose or string-`test`
    scenario (its `steps` / `expect` as text; the result read from `lastResult.status` or `.result`), with
    pass / fail / blocked / stale / retired / untested-by-design / not-run glyphs.
- **Data** — **single column**: a **Diagram | Table** toggle (diagram = `erd.mermaid` in the shared canvas
  wrapper, with a relationship-legend popover; table = one styled table per entity from `erd.table[]`, fixed
  column widths so all tables align). In Table view, **each entity table that has multiple data treatments
  (`erd.mock` sets) gets its own variant switcher** (Schema · its scenarios) that swaps that table's Example
  column.

## The tool and the product are different things (v2.1)

The shells used to paint themselves with the **project's** tokens: `applyRegistryTokens()` wrote the
registry's `--brand` onto `:root`, so an orange project got an orange tab strip and the tool looked like a
different application per project. The boundary is now structural, and `tests/chrome_foundation.py`
guards its shape:

- **`--pb-*` is the tool's vocabulary**, in one file — `pb/template/chrome.css` — injected into all three
  shells at their `PB_CHROME` marker by `render.py` / `serve.py` (the way `runtime.js` is). It is monochrome,
  two weights, hairlines not cards, and **themed**: every colour is a `light-dark()` pair, so the tool follows the
  viewer's theme — **System** (the OS), **Light** or **Dark** — set on `<html data-theme>` by `pbSetTheme()` (absent =
  System; remembered per viewer in `localStorage`, guarded). `pbSetTheme` fires `pb:themechange` on `window`
  (`{theme, dark}`) so a JS painter repaints; the **canvas tokens** (`--pb-canvas-*`, `--pb-node-*`, `--pb-edge-*`,
  `--pb-erd-*`) are `light-dark()` pairs too, and `pbCanvasPalette()` hands them resolved to the Mermaid
  **flow and ERD, which follow the theme**. The registry can never overwrite any of it (`pb-*` is reserved).
- **`.pb-product` is the project's subtree.** Everything a project renders sits inside one — the
  prototype's `.proto-screen`, the design system's demo stages, variant cells and token swatches — and the
  registry's tokens are scoped to it. **The product and the specimens stay light** — `.pb-product` is
  theme-invariant, so dark chrome never changes what the product looks like. The tool opts in to a project value on purpose via `var(--prj-<name>)`
  (the browser mock's favicon and avatar, as real Chrome takes them from the site).
- **Same names, two scopes.** The shell's ~1,400 usages of `--brand`, `--neutral-*`, `--text-*` were not
  renamed: `:root` now gives those names the tool's values and `.pb-product` gives them the project's.
  So anything that is NOT the project's must never sit inside `.pb-product`, and anything that is must.
- **Navigation is a ladder of shapes.** L1 surface = underlined text tab (`.pb-tab`) · L2 segment = washed
  text button (`.meta-subtab`) · L3 view = outlined toggle (`.lg-view`, `.meta-subtabs--view`) · L4 filter =
  pill chip (`.pb-chip`, in the shared filter bar `pbFilterBar`) · L5 item = a row that opens. A shape is never reused across levels.
  Every class, id and `data-*` hook the tests pin was kept; the look changed, the contract did not.

## Design system site (the shell, `pb/template/design-system.html` — served at `/design-system`)

A **second projection of the registry**, not a tab — the component home. `render.py --ds` builds it and
`serve.py` serves it beside the prototype. Every registry component is auto-collected and **every listed component
gets a live, clickable demo** — the shared runtime (`pb/template/runtime.js`, injected into both shells) renders it
with the SAME `renderCmp*` functions the prototype uses, never duplicated. **Token foundations** are separate pages,
one per kind (Colour, Typography, Spacing, Radius, Elevation), as swatches. The layout is a **docs site**: a
navigation tree on the left and **one page at a time** on the right, each a link (`#/c/<id>`, `#/f/<kind>`; the first
component is the default, an unknown hash falls back to it). All pages stay in the DOM, so a demo keeps its state
while you look at another. No breadcrumb. The bar, project button, Project settings and ⌘K are the prototype's
(shared in `runtime.js`), and **dark mode is back** — the site follows System / Light / Dark like the prototype,
while the demo stages, variant cells and swatches stay light (see the section above). The retired `ds_serve.py`
browsed the upstream `.source.json` clone instead of the project's live components.

- **Tree** = **Components** and **Foundations** as plain section labels — no wrapper above them, no counts, nothing
  to expand — under the shared filter bar (search + a Source chip). **Atoms are never listed**: they appear only as
  parts inside the molecule or organism that uses them — except an atom that is **card-shaped** (`shape: "card"`,
  detected by `spec_measure.py`), which is listed as a **Card**. Every row carries its level and a **Local /
  Library** badge (`scope`).
- **Page head** = the shared `pbHeadHTML` head: name · badge + level · id in mono · **Push to Figma**. It carries
  **no description**: the full `purpose` is the closed *Design notes* disclosure at the end of Overview.
- **Overview is the workbench.** A toolbar — a variant picker (enum props), a **device picker** from `meta.devices`
  (the demo's `pb-screen` container answers the chosen device), **Layers**, and a **Code** toggle — over the live
  stage, then *Edit props* (closed), *Tokens used*, *Used in*, *Source* and *Design notes*. **Layers: Anatomy**
  (numbered markers on the live parts) and **Spec** with **Margin · Padding · Gap**, each in its own colour; every
  value is measured live from the DOM and named by its token when one matches. A part's labels show on hover,
  focus or tap, and a **Labels** toggle shows them all. **Code view** is **HTML | CSS** (the live markup; the
  component's `styleSrc` sheet) with copy.
- **Two more tabs.** **Variants & spec** — one live card per variant combination with its own spec table, a value
  that differs from the default variant highlighted. **Anatomy** — a parts table: # · part · type · Required /
  Optional (with the condition) · tokens as copyable chips; instance parts list the child component's own tokens.
- **Push to Figma** is a dialog with two paths: **Copy JSON** (the bridge node JSON from
  `registry_to_figma.build_component_nodes`, for the plugin's *Code → Figma* tab) or **Copy prompt** — a ready prompt
  for Claude Code built on `/pb:handoff --mode=3 --scope=components --component <id>` plus the project's Figma file
  from Project settings, so one component is created or updated through the MCP.

## Memory layout (per project)

- `registry.json` — the database: `tokens` (a **W3C DTCG** document — `{$value,$type}`, flat or nested-with-aliases; resolved to CSS vars by `pb/tools/tokens.py`), `components` (global refs + `local`; each carries a required atomic `level`), `screens`, `meta`, `staleness` *(deprecated — nothing writes it, and the shell stopped reading it in v2.0.0; see D-19 / D-29)*, `flow`/`ia`/`erd` (`ia.rules[]` is where a rule lives, **with the `decision{}` it was made by** — `meta.tradeoffs[]` is retired into it by migration `0010`, and `meta.others` is retired with the sub-tab that read it; both fields stay, emptied, until a major, D-33), `content` *(optional — the glossary + wording deck behind the UX Design → Content segment; absent renders an empty state, so no schema bump)*, `runtime[]`. **Component-first / atomic law:** only `level:atom` render bodies emit raw HTML; molecules/organisms/screens are pure composition via `pbUse('<id>', props)` (enforced by `lint_registry.py` R-LEVEL/R-COMPOSE/R-LEVEL-ORDER, ERROR under `--strict`). Render code is **not** here — each component/screen's `renderSrc` points at a real body file.
- `render/components/<id>.js` · `render/screens/<id>.js` — the render bodies (v1.4 schema 4): real, lintable `.js` files compiled into `prototype.html` by `render.py`. Edit these directly; the registry stays pure data.
- `spec/components/<id>.json` · `spec/screens/<id>.json` — the handoff docs, in the **Specs-plugin shape (schema 13)**: `anatomy` (parts and their types) · `layout` (a tree of part names) · `elements` (per part: `parent`, `styles` — padding, **margin**, itemSpacing, cornerRadius, colours as token refs — and `visibleWhen`, which is what makes a part optional) · `shape` · `measured`, beside `usage`/`uiLogic`; referenced by each entry's `specSrc`. **`tools/spec_measure.py` measures** `anatomy`/`layout`/`elements`/`shape`/`measured` from the live render when `/pb:build` builds or changes a component — never per page load — and leaves the rest alone. Edit them directly; `render.py`'s `load_specs` re-inlines them into the inlined registry (hand-off / Figma-bridge metadata, and the design-system site's Anatomy and Variants & spec tabs). Do **not** re-add inline `anatomy`/`spec` to `registry.json`.
- `logic/components/<id>.json` · `logic/screens/<id>.json` — the logic contract (**schema 11**), referenced by each entry's `logicSrc`. Two halves. **Derived** — `seam`/`handlers`/`disclosure`, rewritten by `logic_extract.py --contracts`; never hand-edit them. **Hand-authored** — `writes[]` (which store slices the item mutates) and `affordances[].why`; no tool ever touches these. Static derivation traces reads but *not* writes, because the mutation happens inside a store helper, so `writes[]` is the one thing a human must state — and the Logic tab's ripple view draws it. `notes[]` holds prose migration `0009` **copied** (verbatim, with a `source` pointer) out of `logicNotes`/`uiLogic`, which are still exactly where they were.
- `runtime/*.js` — the project's own modules, declared in `registry.runtime[]` and inlined **before** every render body; an entry carrying a `url` instead of a `src` becomes a `<script src>` in the head. This is what a project uses instead of declaring a component whose render body returns `''` just to obtain a module scope.
- `memory/constitution.md` — durable rules: Principles + **Stack Lock** + **DS Lock** (lean, rules-only).
- `memory/decisions.md` — the why-log (one entry per decision, naming the `ia.rules[]` rule it produced; gate overrides).
- `design-system/{name}/{name}.md` — the global DS reference (scannable component index + rules R0–R4 + naming contract). Cloned by `/pb:pull-ds`; a sibling `.source.json` snapshots the source (tokens + components) for `/pb:test --drift`, and `ds-catalog.json` holds the **DS Bridge Scan DS** output (portable publish keys + variables + variant/property metadata) that `registry_to_figma.py` reads for the code→Figma bridge. `meta.dsSource` (provenance) + `meta.platform` record where it came from.
- `prototype.html` — rendered view, regenerated from `registry.json`.

## Schema compatibility

Write-path commands (`/pb:build`, `/pb:plan`, `/pb:pull-ds`, `/pb:handoff`, `/pb:init --import`) apply
this check before patching `registry.json`:

1. Read `meta.schemaVersion` from `registry.json` (absent → treat as schema 2).
2. Read `CURRENT_SCHEMA` from `pb/migrations/manifest.py` (currently **13** — 8 = W3C DTCG tokens, 9 = required atomic `level` / component-first, 10 = `anatomy`/`spec`/`usage`/`uiLogic` externalized to `spec/<kind>/<id>.json` sidecars via `specSrc`, 11 = the logic contract via `logicSrc` + the `ia` slice + `registry.runtime[]`, 12 = `meta.tradeoffs[]` collapsed into `ia.rules[]` as decision-carrying rules, 13 = spec sidecars in the Specs-plugin shape — `anatomy`/`layout`/`elements`/`shape`/`measured`, measured by `tools/spec_measure.py`; migration `0011`).
3. If `schemaVersion < CURRENT_SCHEMA`: print a one-line banner —
   `⚠ Schema gap (v<from> → v<to>): <pending version update's describe() text>. Run /pb:update-version.`
4. Proceed — **unless** the current write touches a slice a pending version update changes,
   in which case **stop** and print: `Blocked: run /pb:update-version --apply first, then retry.`

This is the canonical text. Write-path commands reference this section rather than re-stating it.
Read-only commands (`/pb:test --drift`, `/pb:preview`) and exits do **not** carry this check.

## Why (G0.5 spike, 2026-06-05)

Real-tiktoken measurement: **~3–5× cheaper over a build session + free deterministic render +
clean, deduped state** — *not* "17× per tweak." Isolated cosmetic tweaks are ~break-even; the win
is in **structural edits** and **multi-tweak sessions**, where the compact registry stays resident
in context while the HTML monolith cannot.
