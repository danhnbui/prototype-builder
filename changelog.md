# Changelog

All notable changes to Product Builder. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

*Additive, no schema change. On real projects, over a hundred rules carried no structure: they were written
as `kind: "decision"` with prose only, so the Logic tab could show text and a decision log and nothing to
look at. The tab now draws every rule as a stack of visuals, and authoring writes the structure those
visuals need.*

- **Every rule is a visual stack.** A Logic card shows the rule's shape in a fixed order — the lifecycle
  statechart, then Flow, Tables, Values and Effects blocks — instead of prose. Rule text, the decision, open
  questions, history, tests and sources moved behind one **Details** button that opens a right-side drawer
  (Esc, the close button or a click outside closes it). The Values/History tabs are gone.
- **Ten new block types:** `states`, `nav`, `branches`, `async` (flow) · `timeline`, `order`, `ladder`
  (tables) · `gate`, `inputs` (values) · `edges` (effects). Existing blocks gained optional fields: `steps`
  guards and return edges, `matrix` role dots, `scope` unit, `validation` field preview, `formula` split,
  `params` provenance (sourced / assumed / invented), `effects` toast. The state-machine lifecycle is now an
  SVG statechart.
- **Rows show their pattern.** Each row in the Rules list has a pattern glyph and a short preview ("4 states",
  "3 × 4", "prose only"), and the filter bar has a **Pattern** filter.
- **A prose-only rule says so** and names what it looks like, from `PB_LOGIC.shapes`.
- **`logic_shape.py` and `L-SHAPE`.** New `tools/logic_shape.py <registry.json> [--rule ID] [--json]` reads a
  rule's prose and lists the block types it suggests but the rule lacks; `render.py` attaches the result to
  the page and `logic_check.py` reports it as `L-SHAPE` (information only).
- **Authoring writes structure.** `/pb:clarify` §2/§2b, `think-logic` §5, `pb-clarifier` and `/pb:build` no
  longer leave a rule with a detectable shape decision-only: run the detector, author the suggested blocks
  from facts already stated (never invented), and patch or create a rule's blocks when its logic changes.
  `think-logic` §5 now documents all 23 block types and the state-machine fields (`stateField`, `states[]`,
  `transitions[]`, `overlays[]`).

## [2.2.0] — 2026-10-05

*A minor: everything is additive, no command is removed and no schema changes. pb used to start more than
it needed and never clean up after itself. Measured on three real projects in one morning: tests booted
their own server and browser 156 of 183 times; agents hand-wrote about 740 browser scripts; up to four
headless browsers (about 0.6 GB each) ran at once; preview servers never exited, and three of the four
still running were orphans; and nothing that grew — explore rounds, backups, the server log — was ever
flagged or pruned. This release bounds what pb starts and shows what it leaves behind.*

**Two behaviours change, and you will notice both.** `test_run.py` now **reuses your running preview**
instead of booting its own server (it prints `reusing the running preview at <url>`; `--isolated` gets the
old behaviour), and a preview server now **stops itself after 30 minutes** with no browser tab open and no
request (`--idle-exit 0` turns that off). Everything else below is new surface.

### Browsers: a limit, reuse, one run, and one tool to look

*Every test mode launched its own Chromium, every screenshot round another, and an agent that wanted to
see a screen wrote a Playwright script and left a server behind it.*

- **At most 3 headless browsers at once, per machine and user.** Every browser pb opens for tests,
  screenshots, `explore.py check --shots` and `spec_measure.py` (`/pb:build`'s component
  measuring) goes through one door, `pb/tools/browser.py`. A fourth waits
  for a slot (`waiting for a browser slot (3 in use) …`, printed once); a crashed holder frees its slot
  by itself. `PB_BROWSER_SLOTS` sets the limit (`0` = none) and `PB_BROWSER_WAIT` the wait (default 120 s).
  **The limit fails open:** past the wait, one `note:` line says it was not honoured and the browser
  starts anyway, so it can slow a run but never fail one.
- **Tests reuse the running preview.** With no flag, `test_run.py` attaches to this project's `/pb:preview`
  when it is up and boots a private server — stopped at the end — only when it is not. `--isolated`
  always boots the private one; `--attach [URL]` is unchanged.
- **`test_run.py --all`: three modes, one browser.** Functional, roles and server run in one process,
  over one transport, with a fresh browser context per mode. Each prints under its own
  `── test_run.py --all · <mode> ──` header, the run ends with
  `test_run.py --all: functional exit N · roles exit N · server exit N` and exits with the worst code.
  `--json` writes `{"mode": "all", "modes": {…}}`. Single-mode runs print and exit exactly as before. The
  default `/pb:test` battery uses it, and hands the three browser lanes to one `pb-tester` instead of three.
- **`shot.py` — look at a screen without writing a script.**
  `shot.py registry.json --screen <id>` (or `--path /explore/<id>/<slot>`, or a loopback `--url`) reuses
  the preview, opens one browser for every `--viewport` (default 1440x900 and 390x844) and prints the path
  of each PNG, under `.preview/shots/`. `--role`, `--selector`, `--click`, `--wait-for`, `--full-page`,
  `--eval` (prints the JSON result) and `--console` (exit 1 on console errors) cover what the hand-written
  scripts were for. Exit 3 means it could not run — blocked, not passed.
- **Agents are told.** `/pb:test`, `/pb:explore`, `/pb:build`, `/pb:orchestrate`, `/pb:preview`, the
  builder, design-system, explorer and tester agents and the layout, component-build, design-compare and
  sandbox-test skills now say: never hand-write a Playwright script to look at a prototype, never start
  `serve.py` with `&` or `nohup`, never `kill` a preview. The rule is written once, in `CLAUDE.md`
  § *pb bounds its own footprint*.

### The preview server: stops itself, quieter, controllable

*A preview ran until someone remembered it, polled the disk every 0.3 s all day, and the only way to end
it was `kill`.*

- **It exits when idle.** After 30 minutes with no tab connected and no request, it logs
  `idle for 30 min — stopping (explore.py link or /pb:preview starts it again)`, removes
  `.preview/server.json` and exits. An open tab keeps it alive. `--idle-exit MINUTES` (`0` = never) or
  `PB_PREVIEW_IDLE_MIN` changes it. `/pb:preview` and `explore.py link` start it again; `test_run.py` and
  `shot.py` boot a private server for their own run when none is up, and stop it when they finish.
- **Quieter while nobody watches, never stale.** It checks files every 0.3 s while a tab is open or a
  request arrived in the last minute, every 2 s otherwise — and a page request checks first, so a page is
  never rendered from older files than the ones on disk.
- **A burst of saves is one reload.** `--debounce-ms` (default 300; `0` = reload on the first change)
  waits for the saves to settle, at most 2 s. One save still reloads in about half a second.
- **Status and stop without `kill`.** `serve.py --status` prints url, pid, uptime, open tabs and idle
  time (exit 0 running, 1 not); `serve.py --stop` ends it, but only after its health check confirms the
  server is this project's and the pid is the recorded one. Both take `--json`. `/__pb_health` gains
  `clients`, `idleSeconds` and `startedAt`.

### The long run: see it, prune it, no round left open

*Nothing expired. Explore rounds sat open for days; closed rounds, `memory/backups/`, `.pb-backups/`
and `.preview/server.log` only grew; and the health report watched none of them.*

- **`/pb:clean`.** A dry run by default: open explore rounds (with age), closed rounds, `memory/backups/`,
  `.pb-backups/`, `.preview/server.log`, `.preview/shots/`, scratch `render/_candidates/` folders no round
  owns, and the preview server's state. `--apply` on its own does only the always-safe set — removes those
  orphan folders, trims a log over 1 MB to its last 256 KB, deletes the screenshots — and **never** a
  backup or a closed round. **Those go only with a number you give:** `--keep-backups N` (the newest N in
  each of the two backup folders) and `--keep-closed N`. It never touches an open round and never stops a
  server. `/pb:update-version` still never deletes a backup; `/pb:clean --keep-backups N` is the one
  explicit exception.
- **Health budgets.** `/pb:test`'s ranked health report has a `resources` block: the registry's largest
  key, backups, open and closed rounds, the server log, orphan candidate folders and the preview server.
  A crossed budget ranks a line that names the fix (`clean.py --apply --keep-backups 10`,
  `explore.py reject <id>`, `serve.py --stop`). The budgets are `backups_mb` 50 · `backups_count` 20 ·
  `explore_open_days` 3 · `explore_closed_mb` 50 · `server_log_kb` 1024 · `registry_key_share` 0.35 ·
  `preview_idle_min` 60, all overridable in `memory/doctor.json`. It still ranks and never gates.
- **Stale rounds say so.** `explore.py list` shows each open round's age (`· open 5d`) and `STALE` past
  `--stale-days` (default 3); `promote` and `reject` end with
  `still open: <id> (5d, STALE), … — promote or reject each once it is decided`, so a round is never left
  open silently. `.preview/server.log` is trimmed whenever `explore.py` starts a server.

## [2.1.0] — 2026-10-03

*A minor: everything is additive and no command is removed. Four problems from real projects (an HR
fund app, a map-polygon editor, a back-office tool). Information Architecture never appeared unless asked for. `/pb:explore`
could end as three loose HTML files on another port. Internal skills showed up as slash commands. The
Logic tab rendered every rule as paragraphs. Two further rounds then reworked the tool's own chrome
(schema 13): see the first section. Where a later round reversed an earlier line below, that line says so.*

### `/pb:explore` always ends with a link you can open

*Three rounds in a row ended with an editor link to a hand-built `compare.html`. To get something they
could open in a browser, the user had to ask twice.*

- **`explore.py link <id> [--open]`** prints the compare-and-rate page's URL,
  `http://127.0.0.1:<port>/explore/<id>`, after checking that the page and every option frame load. It
  finds the project's `/pb:preview` server, or starts one in the background if none is running.
  `--open` also opens the page in the browser. `/pb:explore` (A3, A4, B4, G-DESIGN) and `/pb:clarify`'s
  IA round now end every stop that shows options with that URL, and never with a file path.
- **The preview server can be found.** On start it writes `.preview/server.json` (url, port, pid,
  registry) next to the registry and removes it on exit, including on SIGTERM. `GET /__pb_health`
  (loopback only) names the registry it serves, so `link` never points you at another project's server
  that took the port.
- **Page rounds: `explore.py init <id> --pages`.** This is for a subject that is not a registry body,
  such as the tool's own chrome or a standalone mockup. That subject is why those rounds were
  hand-built. Each option is a page under `memory/explore/<id>/<slot>/`, served at
  `/explore/<id>/<path>`. Options are compared on the same page, laid out at the chosen device's
  width and scaled to fit, and are rated, checked (`check --shots` included) and gated like any other
  round. `promote` records the pick and archives the round; nothing goes live.

### Chrome rounds 2 and 3 — the Inspector, dark mode, responsive layouts and a hardening pass

*The tool is no longer light only, the Sandbox is an inspector, the design-system site is a component
workbench, and a component's anatomy and spec are measured rather than typed. **Schema 13**: run
`/pb:update-version` (dry-run first) on an existing project.*

**Round 2 — the Inspector chrome**
- **Light, dark, or follow the system.** The tool's colours are `light-dark()` pairs. Choose System, Light
  or Dark in Project settings; the choice is yours alone, kept in your browser. The tab strip, Sandbox,
  design-system site and compare page follow it. **The prototype and the component demos never change**:
  a dark tool does not turn a project's own colours dark. *(Reverses "light only" and "the design-system
  site loses dark mode", both below.)*
- **The project button and Project settings.** The project name left the tab row for a button at the left
  of the bar (initials only on a narrow window, so the tabs stay reachable). **Project settings** edits the
  project name, the **design-system name (required)**, the **Figma file (optional)** and the theme. On
  `/pb:preview` Save writes `registry.json` through the new `POST /api/meta` (this machine and this page
  only); opened from a file, the dialog is read-only and hands out a plain sentence to paste into Claude Code.
- **The Sandbox is an inspector.** An hourglass in the bar (or **S**) opens a panel on the right; **Esc**
  closes it unless you pinned it, and a pinned panel docks and pushes the prototype aside. **Conditions**
  (device, chrome, Compare, Structure tree, role) · **Run** · **Explore**, with **Reset session** in the
  footer. A disabled Explore says why and names the command. **Run** plays an authored scenario in the page
  while the prototype moves, ticking each step pass, fail or blocked.
- **Phone and tablet frames fit.** The whole frame shows, with a 32px margin (24px on a short window), and
  never touches the bar, at 1440×900, 834×1112 and 430×932. It is recomputed on resize and when the
  inspector is pinned.
- **⌘K search** across rules, jobs, components, screens, test cases, content terms and commands.
- **Scan rows and filters.** Logic, IA jobs and Test Cases are one-line rows (id · title · status · kind)
  under a search and filter bar with an "N of M" count.
- **One state layer.** Hover, keyboard focus, pressed and disabled behave the same on all three surfaces.
  Icons are 16–20px with a name on hover and for screen readers, and no card, row or nav item has a left
  accent border.
- **The design-system site, reworked.** The tree is **Components** and **Foundations** — no "Building
  blocks" wrapper — and lists molecules and organisms; atoms show only as parts inside the component that
  uses them, except a card-shaped atom, listed as a **Card**. Every component carries a **Local** or
  **Library** badge. A component page has tabs, and **Push to Figma** offers **Copy JSON** or **Copy
  prompt** (a ready prompt for Claude Code that creates or updates just that component).
- **A component's spec is measured, not typed (schema 13).** The spec sidecar takes the shape the Specs
  plugin uses — anatomy, layout, per-part padding / margin / item spacing / radius / colours, and whether a
  part is optional. `tools/spec_measure.py` reads them from the live render when `/pb:build` builds or
  changes a component, names a value by its token when one matches, and marks a card-shaped component. It
  needs Playwright and says so in one line when it is missing. `/pb:update-version --apply` migrates
  existing sidecars (migration `0011`), keeping what it cannot convert under `legacy`.

**Responsive layouts** *(built in a separate session and committed alongside)*
- `/pb:init` asks once whether the UI adapts to each device (`meta.responsive`; `/pb:build` asks an older
  project once). Size classes: **compact** under 600px, **medium** 600–1023px, **expanded** from 1024px.
- Every place a project renders is a `pb-screen` container, so a component answers the frame it is in, not
  the browser window. A component that changes across sizes carries a sheet (`styleSrc`) written with
  `@container pb-screen (…)`, never `@media`; `product.css` adds `r-*` utilities for swaps that need no sheet.
- `lint_registry.py` adds `R-STYLE-MEDIA`, `R-STYLE-SCOPE`, `R-STYLESRC`, `R-RESPONSIVE`, and applies
  `R-HEX` / `R-PX` inside sheets.

**Round 3 — the polish pass** *(from running the new chrome on a real 90-component project)*
- **Run is grouped and collapsible.** Scenarios sit under their story with pass / fail / not-run tallies and
  a Collapse all. A scenario written as prose (or a string `test`) is listed but not runnable — it says to
  run `/pb:test`. Test Cases now read both scenario shapes, so a project whose scenarios carry a string
  `test`, `steps` and `lastResult.result` shows its real labels and results instead of 204 × "Not run yet".
- **Logic rows open several at once** and open straight to content: no repeated header, a lone Values or
  History section already open, visual blocks always visible. Row and card share one status rule ("to
  resolve" counts assumptions). The filter's **Clear** sits right after the last chip.
- **Information Architecture is vertical** — the map above the jobs, with one filter bar (search · Role ·
  Priority · Screens · Not handled) that filters the jobs and dims the map together.
- **Project Summary is readable.** Prose supports a few marks — `**bold**`, `*em*`, `==highlight==`,
  `{+improvement+}`, `{-problem-}`, bullets and numbered lists — and bolds numbers on its own; there is a
  lead paragraph, numbered principles, and a table of contents only when there are three or more headings.
  `/pb:clarify` and `pb-clarifier` now write the marks (never changing wording; one highlight per field)
  and add `swatches` / `steps` / `cases` / `examples` blocks to a rule whose prose describes them, from facts
  already in the registry.
- **Flow and Data diagrams follow the theme**, as do both kinds of toast; the product's toast uses the
  project's own tokens and no longer overlaps the tool's.
- **The component page is a workbench.** The head is the name, badge, level and Push — the long description
  moved to a closed *Design notes* at the end. Overview has a variant picker, a device picker (the demo
  answers the chosen device), **Layers** (**Anatomy**, and **Spec** with **Margin**, **Padding** and **Gap**
  each in its own colour, labelled on hover, focus or tap, with a **Labels** toggle for all), a code view
  (**HTML | CSS**), *Edit props* (closed), tokens used and where it is used. **Variants & spec** shows one
  live card per variant with its own spec table; **Anatomy** is a parts table with copyable token chips and
  the tokens of any child component. Every listed component has a live demo.
- **Shared building blocks** for the shells: one disclosure, one filter bar, one toast, canvas tokens for
  diagrams, rich text and a page head.

**Hardening** *(the round-2 review and the round-3 gate)*
- **Every registry writer takes `registry.json.lock` and writes atomically** — `slice.py`, the preview's
  settings save, `spec_measure`, the migration runner, `logic_extract`, `lint_registry --sync-elements`,
  `resolve_frame`, `clone_ds`, `/pb:test`'s result save and `/pb:explore`'s IA promote — so two of them
  cannot lose each other's edit. A held lock is refused with a message naming the holder. The lock file is
  git-ignored.
- **`/pb:update-version`** snapshots the spec sidecars with the registry and restores them on failure or
  `--rollback`; **`--rollback` first saves what is on disk to `.pb-backups/pre-rollback.<ts>/`**; the
  latest backup is the newest by modification time; a held lock stops it with exit 1.
- **`POST /api/meta`** answers a bad request with a message and a 400 (never a traceback), refuses invisible
  characters, and treats a non-Figma link the project already has as a warning, not a blocker. The explore
  scores POST is now loopback and same-origin only too.
- **`spec_measure`** has one exit code per cause (1–7, in `/pb:build` §3a), never overwrites a sidecar that is
  not valid JSON, refuses `--write` below schema 13, measures margin, and measures a responsive component
  with its own sheet.
- **A job id, rule id, entity or property name with a quote in it can no longer run script.** Inline
  handlers read `data-*` attributes instead of interpolating into a JS string (`tests/handler_escape.py`).
- **A script that repaints the prototype while you are on another tab** no longer overwrites that tab.
- **Gate results.** Round 2: `pb-tester` 27/30, the reviewer's Medium items fixed in round 3. Round 3:
  `pb-tester` 29/30 (a 430px horizontal scroll in a variant picker, fixed) and the reviewer's M1 and L1–L5
  fixed; the suite is 48/48.

### Added
- **R resets the Sandbox session.** Not while typing in a field, not with Cmd/Ctrl (reload), not on the other
  tabs, not on key-repeat. The menu row shows its key.
- **`tests/chrome_foundation.py`** — a stdlib guard that the tool/product boundary keeps its shape (mutation-tested
  against the original bug).
- **A new rule card in UX Design → Logic**, chosen with `/pb:explore` on the real rules of a
  map-polygon editor and an HR fund app. Top to bottom:
  - **Title and status.** The title states the rule. One pill: `✓ settled`, `N to resolve` or
    `superseded`.
  - **To-do rows.** Each problem is a row saying what is wrong, what to do and which command does
    it. Red means the rule is incomplete or contradicts itself: a matrix gap, a missing state, a
    lineage loop. Amber means something is unanswered: an open question, an unconfirmed assumption,
    an invariant nothing checks, a state nothing sets.
  - **The rule, always open.** A lifecycle draws as state nodes with their conditions, arrows,
    overlay bands and "returns to" rows (vertical on a phone). Then the matrix, the invariants
    (each `checked` or `not checked`), and every structural block.
  - **Values tab.** Swatches, anatomy, examples and parameters.
  - **History tab.** A timeline whose latest entry is the decision (question, options with the
    chosen one marked, why, affects), then amendments, supersessions and sources. An open question
    leads the tab.

  It replaces the SVG state machine, the folded "Decided" line and the "History & sources" drawer.
  A superseded rule folds to its header.
- **Rule blocks.** `ia.rules[].blocks[]` holds a rule's structure as typed blocks, on any kind and in
  any order:
  - `cases` (condition → outcome, with tones)
  - `scope` (acts on / leaves untouched)
  - `placement` (surface → holds / never)
  - `matrix`, `validation` (refusals, messages, codes), `formula` (terms + worked example)
  - `steps`, `params` (thresholds with units), `effects` (writes + other screens), `note`
  - `swatches` (a colour per state, drawn as the real pill), `anatomy` (an identifier in parts),
    `examples` (input → what it renders as)

  Each block draws as a component in UX Design → Logic and exports as a table in `rules.md`. The
  shapes come from reading every rule across the three projects. `/pb:clarify` §2b and `think-logic`
  §5 give an example of each. `logic_check.py` adds **L-BLOCK** (a block the renderer can't draw,
  ERROR) and **L-PROSE** (a long unstructured rule, information only).
- **`/pb:explore` runs on a tool and a compare page.** `pb/tools/explore.py` provides `init`,
  `slot`, `check [--shots]`, `gate`, `promote`, `reject` and `list`:
  - **Manifest.** Each exploration is `memory/explore/<id>.json`.
  - **Overlays.** An overlay may change several bodies.
  - **Rendering.** Options render in memory against the real registry (`render.load_bodies(...,
    overrides=)`), with no temporary copy.
  - **Gate.** Scoring is a gate.
  - **Promote.** `promote` refuses a mixed pick, and refuses a live body that changed since `init`.
- **`/explore/<id>` on the `/pb:preview` server (same port).**
  - The compare page (`pb/template/explore-compare.html`) shows options side by side or one at a
    time, on the project's devices.
  - Its rating panel saves through `POST /__pb_explore/<id>/scores`.
  - `/explore/<id>/<slot>` is one option, live-reloading.
  - The Sandbox → Explore row (previously a disabled stub) lists the open options.
- **`think-direction`, a skill `/pb:explore` loads before it diverges (A1, B4).** It reads the
  project's memory and DS, asks no questionnaire, and writes `memory/explore/<id>.brief.md`:
  - the job, taste position, hard constraints, real content and responsive answer every option shares
  - which of the seven axes the project's rules lock, and the free ones assigned to slots
  - the states table with collision priority, and the `data-*` verbs, handlers and test hooks every
    candidate keeps, so the pick is a drop-in
  - the rubric criteria the brief says matter, and after the verdict the rules learned for `/pb:clarify`

  It distils the design kit's direction explorer; a locked DS beats every default in it. The evidence
  is two real projects' explore rounds and design feedback.
- **`explore.py --ia`, the engine under `/pb:clarify`'s IA round.** `init <ia-id> --ia --options N`
  opens a round with no overlays and no host, and the seven-criterion IA rubric (job coverage · P1
  jobs within 2 taps · hub load · label clarity · no orphan screens · role fit · findability probe).
  - **Structures.** The coordinator writes one `memory/explore/<ia-id>/<slot>.ia.json` per slot:
    label, bet, scheme, five IA axes, the hub and its items, screens with depth / parent / jobs /
    purpose, layer purposes, and the jobs it leaves `unhandled`.
  - **`check`** writes nothing. It fails a structure that does not parse, a job served by no screen
    and not listed unhandled, a hub item or parent that does not exist, a depth that does not step
    by one down the parent chain, and any pair of groupings fewer than 3 of 5 IA axes apart.
  - **The compare page** gains an `ia` mode: the approved jobs on the left as *when / I want to / so
    I can* with role and priority, one tree per option (hub items → child screens → overlays, each
    with the jobs it serves), and every unhandled or unserved job flagged red on both.
  - **`promote`** backs up `registry.json`, then writes only `ia.jobs[].screens[]` (appended,
    deduped), `ia.layers[]`, `meta.navHub` (when the structure names a hub component) and
    `ia.populated`. It never touches `screens[]` / `components[]`. The picked round's folder lands at
    the stable `memory/explore/_closed/<ia-id>/`, where `/pb:plan` §2 reads it. Tests in
    `tests/explore_ia.py`.
- **Shell deep link.** `?screen=<id>&device=<id>&shell=<mode>&embed=1`.
- **`meta.navHub`** names the component or components holding top-level navigation, for example a
  sidebar and a bottom tab bar. The site map's layer 0 is read from it.
- **`/pb:plan --ia [<job-id>] [--into <screen-id>]`**, and an `ia` slice that `/pb:orchestrate` routes
  to `pb-clarifier`.
- **`/pb:report`, a retrospective for the pb maintainer.** The two feedback reports from real projects
  were assembled by reading 3,000- and 10,000-line decisions logs by eye.
  `pb/tools/report.py` (stdlib) counts that evidence instead and writes it as one facts file with a
  fixed section order, each fact with `file:line` evidence:
  - project shape, with every `memory/` file no command owns
  - the decisions log: back-and-forth vocabulary, recurring topics, empty `Alternatives:`, undated
    entries, size against the rotation threshold
  - retired or unknown command names and undocumented flags named in `memory/`
  - explore rounds and their unscored cells, the `pre-*` backup cadence
  - render timings against DESIGN.md's budgets, `--strict` lint counts, stale test verdicts
  - candidate headers and comment-dated layers left in bodies, and the project's own workarounds
  - with `--sessions`, the Claude Code transcripts, as counts and sequences only: never message text

  The command then appends `## Reading` and ranked, tagged proposals for the next release. It is
  read-only on the project and writes only `memory/reports/pb-report-<date>.md`. `--since` windows
  the dated facts. `tests/report_tool.py` runs it on a folder named `proj [x]` and hashes the
  project tree before and after.
- **The build side checks what a component declares, and looks at what it built.**
  `lint_registry.py` adds **R-PROP-DECLARED** (a body reads a `props.X` that `properties[]` does
  not declare; pass-through wiring like `dataNav` or `className` is exempt) and **R-PROP-USED** (a
  declared option the body never renders). Under `--strict` both are ERRORs, R-PROP-USED only for
  `state`; otherwise both warn. Opt-in **`--exec`** (**R-EXEC**) runs every body in node, with `{}`
  and once per `state` option, and fails a throw, a non-string or `''`. With no node it
  prints one line saying nothing ran. `think-layout` now runs job → a component per region → density
  budget → arrange → look at both widths. `design-component-build` gains a states × variants
  checklist and a collision priority. Measured: the two rules flag 17 components and 2 properties on
  one real project, 59 and 4 on another. The golden fixture had both defects (text-input read an undeclared `label` and `type`;
  login-card's `loading` state rendered nothing) and is fixed. Tests in `tests/lint_props.py`.

### Changed
- **The tool no longer wears the project's colours.** `applyRegistryTokens()` wrote the registry's
  `--brand` onto `:root`, so an orange project got an orange tab strip, and three shells carried three
  unrelated token vocabularies (`--brand`/`--neutral-*`, `--ds-*`, `--bg`/`--panel`) with near-miss values
  between them. Now: the tool speaks in `--pb-*` (new `pb/template/chrome.css`, injected into all three
  shells like `runtime.js`), and the registry's tokens are scoped to the subtree that renders the project
  (`.pb-product`). The ~1,400 usages in `prototype.html` were not renamed — `:root` and `.pb-product` give
  the same names different values. `pb-*` is reserved; the tool can opt in to a project value with
  `--prj-<name>` (the browser mock's favicon and avatar). Guarded by `tests/chrome_foundation.py`.
- **A new look for the tool**, chosen with `/pb:explore` from three candidates: light *(round 2 made it follow
  the system theme)*, monochrome, hairlines
  instead of cards, one type family. The bar is underlined text tabs with the project's name; the Design
  system link and Sandbox share one shape. Navigation is a ladder where each level is a different shape —
  underlined tab → washed segment → outlined toggle → pill filter → row — so a click's effect is legible
  before the click. Every class, id and `data-*` hook the tests pin was kept.
- **The design-system site is a docs layout**, not one long scroll: a navigation tree on the left
  (*Building blocks* → *Components* by atomic level / *Foundations*, with a filter — round 2 dropped the
  *Building blocks* wrapper), one page per component
  and per token kind, each a link (`#/c/<id>`, `#/f/<kind>`). It wears the same bar as the prototype, with the
  crossing in the mirrored slot. *(Round 2 reversed this: dark mode is back on both, and the demo stages stay light, so
  a flipping chrome never touches a specimen.)*
- **`e2e_smoke` no longer asserts that `--brand` reaches `:root`.** That assertion was the bug written down as
  a requirement. It now asserts the real invariant: the registry's tokens reach the product, do not reach the
  tool, the tool can opt in via `--prj-*`, and a registry cannot overwrite `--pb-*`.
- **Removed the device captions** ("Mobile 429 × 926") above compare frames. Each frame keeps an accessible name.
- **IA comes out of the default pipeline.**
  - `/pb:clarify` writes `ia.jobs[]` (§1b), as `CLAUDE.md` always said it did.
  - `/pb:plan` §2 runs on every plan: it maps jobs to screens, names the hub, and writes
    `ia.layers[]` purposes.
  - `/pb:init` §1b is optional.
- **Jobs and the IA both live in `/pb:clarify`, behind two gates.** This replaces the `/pb:plan` §2
  IA pass above, where one grouping was authored by reflex. One real project regrouped the same jobs three times
  in five days (five tabs → three → four).
  - §1b's jobs end in **G-JTBD**.
  - §1c has the coordinator author N groupings of the approved jobs (`--ia-options N`, default 3).
    Every pair differs on at least 3 of the 5 IA axes (scheme · hub shape · depth · layer 0 ·
    secondary).
  - The user scores them on the compare page (`explore.py --ia`, `/explore/<ia-id>`) and confirms
    one at **G-IA**. Only `promote` writes `ia.jobs[].screens[]`, `ia.layers[]` and `meta.navHub`.
  - `/pb:plan` §2 now turns the chosen IA into tasks. It stops and names `/pb:clarify` when none was
    chosen, and no longer derives jobs from `spec.md`. `--ia <job-id> --into <screen-id>` places
    one late job.
  - `--skip-ia` keeps the chosen IA as it is. §1 no longer loads `ref-blueprint`, which is
    screen-level and unused for insights.
  - The new internal skill `ref-ia` (the 18th) carries the IA vocabulary, the grouping schemes, the
    constraints that lock an axis, and the seven-criterion rubric with a findability probe that
    replaces tree testing.
- **The site map reads any nav hub.** Hub items can have any key order and either quote style, and
  `key`/`screen`/`to` are all accepted. Nav-atom props (`pbUse('nav-item', {screen: 'x'})`) count as
  edges, so a project that follows R-COMPOSE gets a map.
- **A blank map says why** (no hub / the hub lists no screens / no edges) instead of rendering
  nothing. The IA buttons point at real commands (`/pb:clarify`, `/pb:plan --ia`).
- **Logic cards.**
  - The summary is a one-line lead.
  - The decision folds away when blocks exist.
  - History and sources (supersession, amendments, origin, citations, retired invariants) sit in one
    fold. `stillOpen` stays visible as an *open* chip.
- **Invariants** render on any rule kind and accept `enforcedIn` beside `enforcedBy`. Missing
  enforcement is flagged once per rule, not once per row.
- **Skills are internal.** All 17 set `user-invocable: false`, so `/pb:think-clarify` and the rest no
  longer appear beside the 12 commands. The tab `?` dialogs list commands only.
- **`tests/skill_refs_lint.py`** checks:
  - that every skill is hidden
  - that every skill name used in commands, agents and skills ships, and no retired name is used
  - that every `/pb:<cmd> --<flag>` a shell names is one the command documents

### Fixed
- **Atoms sorted last on the design-system site.** `LEVEL_ORDER[level] || 9` treats `atom` (0) as falsy.
- **The design-system theme bridge ran before any token was applied**, so it only ever read the static defaults
  and never coupled the stage to the project, as its comment claimed. It now runs after, and reads the product scope.
- **Folder names with brackets** (`[HR] Project`). Every glob built from a project path is escaped:
  `serve.py`, `render.py`, `logic_extract.py`, `logic_check.py`, `lint_registry.py`,
  `resolve_frame.py`, `agents_install.py`. Before this, the preview stopped reloading on body edits,
  the site map was blank, and logic checks passed over zero files.
- **Stale names found by the widened lint:**
  - the shell's tab dialogs advertised six skills that don't exist
  - `pb-reviewer` cited a `check-drift` skill
  - `pb-design-system` and `agent-dispatch` named a retired command
  - two IA buttons offered a `--job` flag no command has
- **`rules.md`** exported rules as title plus id only. It now carries the summary, states,
  invariants, blocks, decision and open questions. Its jobs and layers tables read the real fields
  (`when`/`want`/`so`, `name`/`purpose`).
- **A rule with a top-level `status: "superseded"`** now dims. An `affects` array no longer prints
  as `a,b`.
- **The preview server's JSON depth limit no longer depends on the Python version.** Python 3.11's
  parser raises `RecursionError` on deeply nested input; 3.14's parses it. `serve.py` now counts the
  nesting itself (`JSON_MAX_DEPTH`, 64) before parsing a settings save or a score sheet, so every
  version refuses it with the same 400. The count is a single linear pass, so a hostile body cannot make
  it slow.
- **Hardening from CodeQL.** The preview server's page-round files and `explore.py`'s manifest read
  check the real path stays inside the exploration folder; an exploration id can no longer end in a
  newline; `pbMachine` escapes a backslash in a machine name as well as a quote.
- **Tests ran against a folder outside the repo.** `ia_view`, `ui_primitives`, `chrome_states` and
  `chrome_foundation` used a sibling demo project when one existed, so they passed on the author's
  machine and failed in CI. They now build their fixtures from `fixtures/golden`. `spec_measure`'s
  "nothing written" check no longer trips over the `__pycache__` that Python 3.11+ writes beside its
  import shim, and no browser test waits on the web-font or mermaid CDN any more.
- **CI skipped most browser tests.** The e2e job ran a hard-coded five. `ci.yml` now names the
  browser-only tests and the ones with a browser half once, and e2e runs them all; a skip there is a
  failure.

### Housekeeping

- **MIT licence** (`LICENSE`).
- Internal feedback write-ups were removed, and real project names were replaced by neutral
  examples in skills, comments, tests and this changelog.

## [2.0.1] — 2026-10-02

*A patch: CI only — nothing in `pb/` changed for users.*

### Added

- **A release pipeline** (`.github/workflows/pipeline.yml`): test → version → release →
  deploy-prod. Every PR runs gitleaks over the full history, semgrep's OWASP Top 10 and trivy, and
  checks that the version is bumped as far as its Conventional Commits ask for
  (`python3 .github/scripts/bump_version.py auto` does the bump). Merging an unreleased version tags
  it, opens a draft GitHub Release, and waits for a required reviewer before publishing.
  `release.yml` is retired into it.

### Fixed

- **The render-determinism check was a coin flip on the clock.** It compared raw bytes of two
  renders, which differ in the second-resolution `pb-shell` stamp whenever the renders straddle a
  second. `tests/render_determinism.py` now compares with the timestamp normalized, and asserts the
  stamp is present and names the current version.

## [2.0.0] — 2026-09-20

*A major, for one reason: **twenty-four commands became twelve and the old names were deleted, not
aliased** — see Removed below, and [docs/upgrade-to-2.0.md](docs/upgrade-to-2.0.md) to move a project
across. Alongside that: `/pb:test` stops grading its own homework, a trade-off is stored as the rule
it always was (**schema 12**), the UX Design tab is restructured into five segments, and the `flow` /
`erd` slices stop being something you had to remember to refresh.*

### Removed — BREAKING

**Twenty-four commands became twelve, and the twelve retired names were deleted rather than
aliased.** This is the whole reason 2.0.0 is a major. An old name is not redirected — it reports
that no such command exists. Nothing in an existing project stores these names; they live in habits
and in team docs.

| Retired | Run instead |
|---|---|
| `/pb:flow` · `/pb:sync-flow` | `/pb:plan --flow` |
| `/pb:data` · `/pb:sync-erd` | `/pb:plan --data` |
| `/pb:check-drift` | `/pb:test --drift` |
| `/pb:validate` | `/pb:handoff --tier=host` |
| `/pb:preview-ds` | `/pb:preview`, then the `/design-system` route |
| `/pb:build-check-design-system` | `/pb:build` — now §3a of the loop, automatic |
| `/pb:build-figma-handoff` | `/pb:handoff` → mode 3 (Figma) |
| `/pb:handoff-close` · `/pb:hand-off` | `/pb:handoff` → mode 1 (everything) |
| `/pb:handoff-dev` | `/pb:handoff` → mode 2 (engineering) |

[AGENTS.md](AGENTS.md) §2 requires a backward-compat alias for every rename, to be dropped only in
a later major. These shipped without one, so by §2's own logic the release carrying them is that
major (**D-34**). The aliases are not added retroactively — a major is precisely where a removal is
allowed to land, and stubbing twelve commands would buy a smaller version number in exchange for
twelve more files to keep in step.

**Upgrading an existing project takes about five minutes:
[docs/upgrade-to-2.0.md](docs/upgrade-to-2.0.md).**

### Added

- **`/pb:test` plans the run, then delegates the grading (D-32).** D-31 stopped a verdict from outliving
  the code it described; this stops it from being written by the context that authored the design. Two
  steps of a test run are model judgment — the constitution-drift audit and the summary — and both ran in
  the same window that built the thing under test, which reads its own intent and scores the intent.
  - **§2a — a plan of record.** Before anything executes, `/pb:test` writes
    `memory/test-plans/<stamp>.md`: **one item per test case**, each a binary question, admissible only
    if it opens *Does/Did/Is/Are/Was*, names the single observation that settles it, needs nothing from
    the spec or the conversation to answer, and is phrased so **`yes` means the check held**. Uniform
    polarity is what lets a plan be tallied mechanically. The question belongs to the **lane** and is
    stated once in its heading, so a plan is a handful of small tables — `| # | Scenario | Answer |
    Evidence |` — rather than a page of restated sentences.
  - **Never an open question.** *Should · Consider whether · Is it correct that*, anything answerable
    *it depends*, anything asking whether coverage is **sufficient** or **worth adding**, anything asking
    for a rating — rejected and rewritten. A check that cannot be phrased admissibly produces **no item**:
    project health ranks rather than judges, so it contributes none. **`blocked`** is not a third answer —
    it is an item never reached, it names its blocker, and it never counts toward a pass.
  - **§2b — sonnet subagents.** `pb-tester` on `model: sonnet`, one per lane, ≤25 items each, ≤8 per run,
    dispatched in one message. Each gets the plan path, its item ids, the registry and its lane's command —
    and explicitly **not** the spec, the plan, the decisions log, the prior `lastResult` (*"it was green
    last time"* is the same bias by another door), or any framing from the authoring session. Each returns
    `<id> · yes|no|blocked · <evidence>` rows and nothing else; recommendations are not a tester's output.
  - **§11 — reconcile, don't summarize.** Every plan id gets exactly one answer, an unanswered item is
    `blocked` rather than dropped, evidence is quoted rather than paraphrased, and a returned `no`
    **cannot be overturned** — disagreement earns a new row and a fresh agent, with both shown.
    `--no-delegate` self-grades and stamps every judged item as such.
  - **The chat output is short.** Rows are filled back into the plan file in place; what prints is a
    header, one line per `no` or `blocked`, and `<N> items · <Y> held · <Z> failed · <B> blocked`.
    Held items are a count and a file path — a report that prints 38 successes buries the three lines
    worth reading. Evidence is one line each: the observation, never a narrative.
- **A trade-off is a rule, so it is stored as one — schema 12 (D-33).** v2.0.0 moved `meta.tradeoffs[]`
  into UX Design → Logic *because* a trade-off is a rule captured at the moment it was decided (D-30),
  and then left it as a separate array, with a separate view, a separate capture step and a separate
  renderer. The reasoning arrived at the right place and stopped one step short. It is now a field on
  the rule:
  - **`ia.rules[].decision{ question, options[], chose, why, status?, supersededOn?, affects? }`** —
    any rule, any kind, and the card draws it. `options[]` carries what **lost**, which is the one
    thing a rule cannot state for itself and the entire reason this was ever a separate record.
  - A fourth kind, **`decision`**: a rule you have settled but not yet expressed as a state machine, a
    matrix or a constraint. Upgrading it later is a `kind` change and the block stays.
  - `[SUPERSEDED <date>]` in a title becomes **`decision.status`**. That convention existed because the
    schema had no status field; now it does. A title written the old way still renders dimmed.
  - **Migration `0010`** converts every trade-off, stamping `origin: "tradeoff"` so the rollback can put
    it back. A rule edited since the migration is kept as a rule and reported, never demoted. The field
    is **emptied, not removed** (`AGENTS.md` §3), and `down()` refills it byte-for-byte.
  - `/pb:clarify` no longer has a trade-off task. It writes the rule and its decision in one act, and
    still appends one `decisions.md` entry each — now naming the rule id it produced.
  - **The Others sub-tab goes with it.** `meta.others` had no schema, no writer and no check, and both
    slices that own its content (`content`, `ia.rules[]`) exist. The field stays in the registry;
    removal waits for a major.
  - **A project that has not migrated loses nothing.** Its trade-offs still render in Logic → Rules,
    through the same decision renderer, under a banner naming the one command that converts them. D-30
    refused to hide 12k characters of someone's terminology; this refuses to hide 22 of their decisions.
- **Stale-claim detection — a verdict and a rule now carry what they were computed from (D-31).**
  Three surfaces asserted things nothing re-checked. On a real project three scenarios read
  `3/3 passing` after **141 of 141** render bodies had changed underneath them; `ranAt` was written
  but read by nothing except a tooltip.
  - `logic_extract` emits **`itemHash`**, a digest per item of its own body plus everything it
    composes. `/pb:test` stamps `lastResult.inputs` for the screens a scenario actually exercises,
    and the shell shows a verdict whose inputs moved as **stale** (`⟳`), never as pass. That project
    now reads `0/3 passing · 3 stale`, which is the true statement.
  - `logic_extract` emits **`stateWriters`**: which declared states the code actually puts the system
    into — but only when the rule declares `stateField` (the property holding the state) and marks
    computed states `derived`. Without it the check makes no claim, because an unqualified scan
    cannot tell a domain state from a UI variant sharing the word, nor an assigned machine from a
    derived one.
  - **`L-RULEREF`** in `logic_check.py`: every function name a rule cites — `implementedBy[]`,
    `readers[]`, `implemented[].name`, `invariants[].enforcedBy` — must resolve in the derived graph.
- **Compare — one screen, two devices, at their real widths.** The Sandbox menu gains a **Compare**
  switch: turn the mode on and the same screen renders twice, side by side, on exactly one more
  device (the picker appears under the switch, with the primary and the unsupported sizes
  disabled). Switching it on chooses the first available second device, so the toggle does
  something the moment you flip it rather than arming an empty state. Each frame lays out at
  its **true CSS width** (1280 really is 1280, so the wrapping and the media queries are the real
  ones) and the pair shares **one** `scale()`. That last part is the whole design: fitting each frame
  to its own box would draw a 429px phone the same size as a 1280px laptop, which destroys the only
  thing a side-by-side is for. Each frame is captioned with its device and size, and choosing the
  compared device as the primary drops the compare rather than pairing a device with itself. A
  `ResizeObserver` on the stage re-fits the pair when the structure panel takes the width — a single
  frame rides that out in CSS, but a scale computed in JS at render time does not.
- **Two frames, one session.** Both frames show the same screen, so anything that happens inside that
  screen has to happen in both or the comparison is a lie. Screen navigation re-renders and always
  did; everything under it did not — a wizard step, a revealed password, a typed value, a validation
  error each landed only in the frame that was clicked. A `MutationObserver` re-serialises the acting
  frame's `innerHTML` into its twin, which is general by construction: both frames hold identical
  markup, so an element's twin is the node in the same position, and the mirror carries whatever
  `registry.runtime[]` invents next without knowing a single verb by name. The three things
  `innerHTML` does not hold are carried as the DOM properties they are — `value` / `checked` /
  `selectedIndex` on an input and change listener, `scrollTop` / `scrollLeft` on a capturing scroll
  listener. **Scroll is half of in-page navigation**: a jump to a section, a `scrollIntoView`, a
  re-render that returns to the top all move one frame, and the twin, put back where it was, was
  simply not looking at the content that had arrived — the content reached both devices, only one of
  them showed it. It carries as a **proportion**, since two frames of different widths lay the same
  screen out at different heights.
- **Two frames, two radio groups.** A radio button group is every radio sharing a name *and a form
  owner*, across the whole document — so two frames of one screen is two of every radio in it, and the
  browser treats them as one group where only one can be checked. The second frame's radio silently
  unchecked the first frame's, with no event and no mutation to notice it by. A project that drives
  its in-page navigation from CSS-only radio state — `:has(#view-a:checked) .view-a { display:flex }`,
  which is how a prototype gets tabs and master-detail without a line of JS — therefore rendered its
  content in **exactly one** of the two frames, and the other looked empty. It was not empty: it was
  showing a view that had lost its radio. Each secondary frame now gets an empty `<form>` of its own
  and its radios point at it, which is the other half of what defines a group and the half nothing
  selects on: same names, same ids, the project's CSS untouched. It is re-applied after every mirror
  copy, because `innerHTML` brings the original attributes back with it.
- **One frame drives the session.** Two frames in one document means every id in a screen body exists
  twice, so a project's own handler splits down the middle: `this` and `closest` find the frame that
  was clicked, `document.getElementById` always finds the first one. A click in the second frame ran
  half in each — the pane switched in frame A while the tab highlight moved in frame B — and the
  mirror then copied one half over the other, leaving **both** frames showing a state that never
  existed. A click in a secondary frame is replayed on the primary frame's twin node, so the handler
  runs once, in one frame, with `this` and the ids agreeing, and the mirror carries the result back.
  The second frame stays live; it is just not a second session, which is what the shared id space had
  already decided. What the browser drives itself is left alone — a text field, a select and a label
  keep their own click so the caret stays in the frame being typed in, and ⌥-click stays frame-local
  because the inspector is read-only.
- **The Prototype tab's browser chrome is a Chrome window.** Chrome's own metrics and Chrome's own
  neutrals — window controls, a tab with the concave notch where it meets the toolbar, real icons in
  place of the `‹` and `⟳` glyphs, and an omnibox that de-emphasises everything but the host, the way
  Chrome does. The greys are deliberately **not** registry tokens: painting the tab strip in
  `var(--neutral-10)` made the browser take on the project's brand, so in a screenshot you could not
  tell where the product ended and the window began. Only the favicon and the profile avatar carry
  the project's colour, because in real Chrome those are the two things the site supplies. `app` gains
  the same window controls. Furniture that does nothing (forward, extensions, the kebab) is inert and
  `aria-hidden` rather than `disabled`: it is not a control pb declined to implement, it is Chrome's.
- **A phone now runs a phone's browser.** `browser` + mobile rendered the desktop tab strip inside a
  429px bezel — the shell's one plainly impossible screenshot. Mobile gets a status bar and a single
  address pill with a tab counter. Tablets keep the tab strip; iPads really do show one.
- **…and a tablet runs a tablet's browser.** The tab strip was the right call; everything around it was
  the desktop's. `browser` + tablet drew macOS traffic lights, a window kebab and an extensions puzzle
  inside an iPad bezel, and — because only the desktop branch drew any of it — the tablet was the one
  device whose **OS status bar disappeared** the moment you switched Chrome from App to Browser, which
  is backwards: a status bar belongs to the device, not to the chrome mode. A tablet browser is now the
  status bar, a tab strip and a toolbar, with the window manager's furniture gone. The **Dynamic Island**
  went with it: it is a phone's camera housing, and an iPad does not have one — it was a black pill sitting
  in the middle of every tablet status bar for no reason anybody could name.

- **A third rule kind — `constraint`.** `ia.rules[]` could draw a state machine or a matrix and nothing
  else, so a rule that is neither — most scoring rules — rendered as a title over a paragraph with the
  enforcement point left unnamed. A `constraint` rule carries `invariants[]` (`must` / `enforcedBy` /
  `when` / `message?`) and draws them as a table, each `enforcedBy` linking into the derived ripple.
  An invariant with **no** `enforcedBy` renders as a warning: a stated rule nothing enforces is the
  finding, not a blank cell. Unknown kinds still degrade to title + summary.
- **Content — the fifth UX Design segment, and the `content` registry slice.** One place for the words
  the product uses. `terms[]` is the glossary: what a domain word means, what else the team says for it
  (`aka`), and what it is deliberately never called (`avoid`). `strings[]` is the wording deck: the
  canonical text for every action, status, label, title, empty state, toast and error, grouped by `kind`.
  A term may carry `rule: "<ia.rules id>"`, which links it to the Logic segment and back.

  Both halves are **hand-authored** — no tool derives either — so the segment runs exactly one check, and
  runs it on authored data only (D-08 Kind A): a wording, **or a declared rule's state or overlay label**,
  that uses a word another term banned. Scanning rule labels is the half that earns its keep: a rule is
  transcribed from a spec once and then nothing re-reads it, so its labels are the wording most likely to
  drift from the code. On a real 143-item project it caught two on the first render.

  `content` is **optional and additive** — absent, the segment renders an empty state, so per
  `pb/migrations/manifest.py`'s own rule (bump on *a new required field, a shape change, a renamed key*)
  **`CURRENT_SCHEMA` stays at 11**. `slice.py` gains `content` as a dict kind, so `get content terms`
  reads the glossary without dragging the wording deck along.

  **Known gap, stated plainly:** nothing *writes* `content` yet — no command, agent or tool authors it.
  It is the fifth registry slot pb ships with a reader and no writer (`ia.rules[]`, `ia.jobs[]`,
  `logic/*.writes[]`, `logic/*.affordances[].why` are the others). Seeded by hand until that is fixed.
- **The logic contract — `logic/{components,screens}/<id>.json` via `logicSrc` (schema 11, D-28).**
  Two halves, and the split is the point. **Derived** — `seam`, `handlers`, `disclosure` — is written
  by `logic_extract.py --contracts` and rewritten every run, so it cannot drift from the code it
  describes. **Hand-authored** — `writes[]` and `affordances[].why` — is never touched by a tool,
  because static derivation traces which store slices a file *reads* but not which it *mutates*: the
  mutation happens inside a store helper. `writes[]` is the one thing a human has to state, and the
  Logic tab's ripple view draws it beside the derived reads.
- **`registry.runtime[]` — a project's own module layer.** Real `.js` files inlined **before** every
  render body, plus declared third-party dependencies (`url` → a `<script src>` in the head). This
  retires the fake-component hack: on the project this was measured against, three components whose
  render bodies return `''` carried **2,567 lines and 103 functions** purely to obtain a module scope,
  and a parser had to be hand-injected by editing the shell. `/pb:preview` watches `runtime/**/*.js`.
- **Two runtime verbs that earned their place.** `data-machine` / `data-step` (with `data-step-pane`,
  `data-step-go`, `data-step-initial`, `data-step-dot`, and `pbSetStep()` for the transitions a click
  cannot express) replaces four copies of one six-state wizard carrying **63** bespoke
  `data-<prefix>-state` attributes and a per-copy CSS block. `data-preserve` marks what survives a
  re-render — `pbPreserve(fn)` captures, re-renders, restores, then fires `input`+`change` once
  everything is back — retiring **24** call sites that each passed a hand-maintained list of element
  ids. Both live in `runtime.js`, so both sites get them.
- **The `ia` slice** (`jobs[]` in the three-field JTBD form, `layers[]` with one declared purpose each).
- **`logic_extract.py --contracts`** (with `--dry-run`): refreshes the derived half, leaves every other
  key exactly as the author wrote it, rewrites nothing when nothing changed, and points the registry at
  any contract it does not yet reference.
- **`meta.shell: 'none'`** — a third chrome option beside `browser` and `app`: the screen renders
  flat, with no tab strip, no synthesised URL and no window frame. The browser metaphor is set
  dressing on an internal back-office tool and costs 77px of height. Tablet and mobile keep their
  device frame and status bar — that is a phone, not a browser.
- **`decisions_rotate.py`** — the why-log rotation D-21 specified and the first pass of this release
  did not ship, while five files told users their glob must be `decisions*.md` **because** rotation
  moves older entries. Size-triggered (500 KB, never the calendar), whole entries chosen **by their
  own heading date** — a real log runs 22 August entries, then 86 July, then 78 August, so "the
  tail" is not "the oldest" — undated entries pinned, every touched file backed up, and the whole
  `decisions*.md` family compared entry for entry afterwards. On a real 875 KB / 187-entry log:
  497 KB live + 378 KB archived, all 187 byte-identical. `lint --report` names it past the threshold.
- **`R-TOKENREF`** — a lint rule for the `var(--x)` that nothing will ever set. An unresolvable
  custom property makes the browser drop the whole declaration, silently; pb counted *unused* tokens
  and never asked the question that actually breaks a screen. Three things count as producers (the
  project's tokens, the shell's own 58, and a property a body sets itself) and a fallback changes the
  question — `var(--x, y)` is a finding only when `--x` exists and resolves to **empty**, the one
  case where a fallback does not apply. Seven of its nine tests are a false-positive corpus.

### Changed

- **UI Logic Trade-offs moved from Project Summary to UX Design → Logic (D-30).** A third view beside
  Rules and Ripple. A trade-off *is* a rule captured at the moment it was decided, carrying the one
  thing no rule can — the options that lost — so it belongs beside the rules it produced rather than
  in a tab read before building and never during. `meta.tradeoffs[]`, `/pb:clarify` and the
  `memory/decisions.md` mirror are all unchanged; only where it is read moved. The renderer now
  honours a `[SUPERSEDED <date>]` prefix on `title` (dashed, dimmed, chipped) — a convention projects
  invented because the schema has no `status` field.

- **Flow and Data ride the trio (D-29).** After a **trio-touching** patch (a screen, a component,
  logic), `/pb:build` reconciles the `flow` and `erd` slices **in the same turn** — a new screen gains
  a node, its edges and a story stub; a removed one loses them; a new data-bearing field gains an
  `erd.table[]` row. Canonical rule: `CLAUDE.md` § *Auto-sync*; the step is `build.md` §4.5, and
  `/pb:orchestrate` runs it **once per wave**, between apply and render. Four bounds keep it cheap:
  reconcile never regenerate, populated slices only, never re-author, defer restructuring. **Non-trio
  tweaks still skip it** — load-bearing rule 3 is unchanged. `/pb:flow` and `/pb:data` remain the
  *authors* of their slices (first population, the five-lens QA pass, any restructuring).
- **UX Design is four segments** — Logic · Information Architecture · User Flow · Test Cases. Test
  Cases is promoted out of the User Flow aside into its own segment; Information Architecture becomes a
  50/50 job list | site map split with the role filter inside the job list, and JTBDs that no screen
  serves are flagged there.
- **`slice.py` gained `flow` and `erd` dict kinds**, so the reconcile can read `flow mermaid` (~15
  lines) without dragging every story's `scenarios[]` into context.

### Deprecated

- **`meta.others` (D-30).** The only registry field with no schema, no writer and no check — a raw
  HTML string. It had become the dumping ground for exactly the things that had no home: on a real
  project, 12,466 characters of roles, status sets, entities, terminology, fixed column wording and
  business rules. Those now have `content` and `ia.rules[]`, so `others` is the symptom, not a
  feature. The field stays in the registry (`AGENTS.md` §3) and its tab renders **only while it is
  non-empty**, under a banner naming the slice that owns each kind of content — deprecating it by
  silently hiding 12k characters of someone's terminology would be data loss, not a tidy-up.

### Fixed

- **Chrome · None did nothing.** `PB_SHELL_OPTS` offered the third option, `PB_SHELLS` mapped it, the
  CSS styled it and `protoChrome` honoured it — and `setProtoShell` still read
  `v === 'app' ? 'app' : 'browser'`, quietly coercing the third value back to the first. Four layers,
  three of them agreeing, and the button lit up while the tab strip stayed. It validates against
  `PB_SHELLS` now. A second, **two**-option chrome toggle was still being built a few lines above in
  `renderPrototype` — dead since v1.9 along with the rest of the header-tool builders, and the reason
  a third option was easy to miss; all of it is gone, with the CSS that dressed it.
- **The structure tree opened where you could not see it, then closed itself.** Its toggle lives in
  the Sandbox popover, and the popover is anchored over the exact strip of page the panel slides
  into — so flipping the switch appeared to do nothing. The panel you could not see was then
  dismissed by your next click anywhere in the prototype. Toggling now closes the menu so the result
  is visible, the click-outside dismissal is gone (a panel you explicitly opened should not vanish
  when you use the thing it describes), and the panel has its own heading and ✕.
- **The scenario list read "scenario" for every row.** It keyed on `sc.title`, a field the authored
  shape has never had — `/pb:plan` writes `{ text, category, test }`. The menu now lists each runnable
  scenario by its **description**, the same sentence UX Design → Test Cases shows, with the last-run
  glyph in front of it; picking one jumps to the screen the scenario starts on and names it, instead
  of being an inert list. The row is called **Scenario testing**: nothing about it involves a terminal.
- **Reset session sat above the controls it resets.** It is last in the box now, under a divider.
- **The structure panel described the page you were looking at.** Under every screen it listed each
  entry in `elements[]` and the component it points at — three lines of description per screen, and
  the half most likely to be wrong, since `elements[]` is a declaration that drifts (`R-COMPOSE-MATCH`
  exists because of it). It is **page names only** now, indented by depth in the derived nav graph so
  a screen sits under whatever reaches it, flat when a project has no graph. ⌥-click already answers
  *what is this element*, and it answers from the DOM.
- **Chrome and Device disagreed about what "selected" looks like.** Two segmented picks in the same
  menu, one filling solid brand and one a soft tint — the soft one was an override added for the
  popover and never applied to its neighbour. Stated once now, for both.
- **A long scenario list was unreadable.** Scenarios are authored as full sentences, so forty of them
  made a wall of prose in a dropdown. They are grouped by the story that owns them (`<optgroup>`, so
  the scope is stated once rather than implied per row) and each is clamped to its first line, with
  the whole sentence in the option's tooltip.
- **`pbProtoSubmit` scoped validation to `.proto-device`, a class the shell has never emitted.** The
  fallback therefore reached `document` every time. With one frame that was the same thing; with two
  it made frame B's submit validate frame A's empty inputs and refuse to navigate. It scopes to
  `.proto-screen`. `pbResetSandbox` and `pbApplyRoleGating` were `#proto-frame`-only for the same
  reason and are now frame-agnostic — an ungated second copy of a gated screen would show a role
  exactly what it may not see.
- **A rule's state machine drew scope and timeline as the same kind of thing — and with three
  overlays the bands collided with the states.** The state baseline was a constant (`y = 74`) while
  the overlay stack grows per band, so the third one landed on the boxes. Beyond the collision, a band
  was a rounded pill overshooting its span by a few pixels, which made *"holds across all five states"*
  and *"holds across three"* look alike, and its label floated in the middle of a full-width band,
  attached to nothing. The two are now different things on the page: the bands get their own **Scope**
  zone with a rule under it and the states are captioned **Timeline**; each band aligns **exactly** to
  the boxes it spans, with square corners and solid end caps (a span has ends, a pill does not) and its
  label at the start of the span; bands sort **widest first**, so a narrower scope sits visibly inside a
  wider one, and the table's overlay rows follow the same order; and the baseline and SVG height are
  computed from the stack instead of guessed.
- **Test Cases is a master–detail split: cards on the left, the case at 50% width on the right.** On the
  reference project the tab stacked 22 coverage notes (17,249 chars, longest 2,057) and 6 scenarios
  (7,307 chars, longest **2,404**) as full paragraphs — one scenario alone filled a screen.
  - **The card** carries the verdict glyph, the lens chip, the date, a two-line claim and one dim line
    saying what running it involves (`from quan-ly-chu-ky · 1 step · 4 expects · as hr`). Clicking it
    opens the panel; clicking it again, or `Esc`, closes it. **The two columns scroll independently** —
    the segment owns the viewport height rather than sitting in the page scroller, so reading a long
    case never drags the list out of view and the panel's close button stays pinned; under 900px the
    split stacks onto the page's own scroller. The claim is the authored `title`, else it
    is derived — the text's first strong break at least 24 characters in, capped at 110, never ending
    inside a parenthesis. The minimum is the part that matters: breaking at the first delimiter yields
    *"Cổng trọng số"*, a fragment that identifies nothing. Delimiters are punctuation, not words, so it
    holds in any language, and the claim is always a **prefix** of the authored text, never a paraphrase.
  - **The panel** is the only place the whole text appears, and it appears structured: the verdict
    (story · verdict · detail · last run), **How it runs** — the `test{}` block said as sentences, with
    the asserted value bold (`The frame reads **"Chưa bắt đầu"**`, `No console error fires`) — and the
    author's notes.
  - **The notes keep the structure the author already wrote.** Newlines separate blocks, `·` opens a
    bullet, backticks become code, `**…**` is honoured, and a block over 400 characters with no newlines
    at all — all 22 gap notes — is broken where a sentence starts with an ALL-CAPS run, because that is
    how this author marks a new thought (`CẬP NHẬT 2026-08-10`). **Emphasis is reported, never
    invented**: a run is bold because the author capitalised it. Single short caps words are skipped
    (HR, KPI, UI and PRD are nouns, not shouting) and hyphen guards keep it out of identifiers, so
    `T-ROLE-EL` never renders as T-**ROLE**-EL. The longest note yields 9 bold runs in 2,057 characters.
- **`coverageWarnings[]` gains optional `title` and `status`.** `status` is `open` (default) ·
  `resolved` · `accepted`; only `open` rides the warning rail and counts in the tally, while settled
  ones stay visible below a divider. Two of the reference project's 22 notes open with *"ĐÃ GIẢI
  QUYẾT"* — resolved weeks earlier — and several more record deliberate decisions, yet all 22 counted
  as open gaps. A fixed gap and an accepted one are both records worth keeping; counting them as open
  makes the number wrong. Both fields are optional and additive: a project that authored neither
  renders and counts exactly as before.
- **`render.py`'s logic cache ignored the extractor itself.** `_logic_key` fingerprinted the
  registry and the render bodies but not `logic_extract.py`, so teaching the extractor to derive
  something new left a long-running `/pb:preview` serving the old graph forever — the data never
  changed, so the cache never missed. The same staleness bug as D-31, one level up.

- **`/pb:update-version` escaped every non-ASCII character** it wrote (`json.dump`'s default), so a
  migration on a project with non-English content rewrote every line that had any and inflated the
  file — measured at 900 KB → 1.06 MB on a real registry, for a migration that changed 126 keys. It
  now writes UTF-8, and reads and writes every file with an explicit encoding.
- **`runtime.js` was physically duplicated into `prototype.html`** — 291 lines existing twice,
  kept in step by a test rather than by the build, and this release had grown them from 156. Both
  shells now take the runtime through the `/*__PB_RUNTIME__*/` marker `design-system.html` already
  used: `prototype.html` drops **7,062 → 6,774 lines** and the drift class goes away. Removing it
  exposed a bug it had been hiding — `logic_extract` learns the shell's globals by reading that
  file, so `pbUse` moving out made **every composed body in every project** report `L-UNDEF`. The
  extractor now reads the shell and `runtime.js` together, which is what the rendered page is.
- **The golden fixture referenced two custom properties that do not exist** — `--space-1` (its
  space ramp starts at `space-2`) and `--text-xs` (the shell's name is `--font-size-xs`), so the
  `text-input` component's gap and error-text size had been silently inherited. Found by
  `R-TOKENREF` on its first run.
- **The prototype inlined three graph fields nothing on the page reads** — `handlers[].bodyHash`
  (the largest single field), `handlers[].localCalls` and `items[].shellVerbs`, all of them for
  tools rather than for the shell. `build_html` now inlines a projection: **50 KB off every render
  and every hand-off**, with the full graph unchanged for `logic_check --freeze`.
- **`test.roles` now scopes the shell's scenario list**, not just `test_run.py`'s execution — the
  role half of D-27 reached the runner but not the list a reviewer reads.
- **A Mermaid `[[subprocess]]` node was painted input-purple** while the legend promised
  subprocess-grey. Mermaid emits both as a `<polygon>` with no `<line>`s, so the point count is the
  only thing telling them apart.
- **The DS site's runtime drift-guard checked three canary lines**, which pass happily while a helper
  added to `runtime.js` is missing from `prototype.html`'s physically duplicated copy. It now compares
  the entire block, byte for byte.
- **`slice.py list` fell through to the tokens tree** for any dict kind but `meta` — latent before this
  release (only `tokens`/`meta` existed), surfaced by adding `flow`/`erd`. Each dict kind now lists its
  own keys; `tests/slice_cli.py` guards it.
- **The IA segment threw away a site map it had already derived.** `pbRenderIA()` returned the "No jobs
  yet" empty state for the *whole* tab whenever `ia.jobs` was empty — but the site map is derived from
  the nav graph and needs no authored job at all. On a real 143-item project with **10 screens placed,
  hubs and overlays resolved**, the tab rendered nothing. The two columns now answer for themselves: the
  map draws whenever `nav.depth` has screens, and "No jobs yet" is confined to the job-list column.
  `pbRenderSiteMap` tolerates an absent `ia` (layer names fall back to `Layer <n>`), and every node
  keeps flagging itself `no job`, so an unauthored IA reads as honestly incomplete rather than absent.

### Notes

- `staleness{}` **stays in `registry.json`** per D-19 / `AGENTS.md` §3 ("never remove or repurpose an
  existing field in place"). Only the shell's reader is gone.
- **Schema 10 → 11.** Run `/pb:update-version --apply`. Migration `0009` is additive and **copies**
  prose — `logicNotes` and `uiLogic` are not deleted, not moved, not one character rewritten — which
  makes it pb's first information-lossless rollback. Proven on a copy of a real 143-item project:
  apply, roll back, and the whole directory is byte-for-byte what it was.
- Three verb candidates were **rejected on measurement**, not on taste. `data-save` — an attribute
  cannot express the project-specific middle of a save. `data-group`/`data-panel` — it would replace a
  `:has()` mechanism with **0** R1/R2 violations across 222 uses, which is a downgrade. `data-bind` —
  deferred.
- No deterministic test can assert that a model reconciled a flow; the trio / non-trio / unpopulated
  rehearsal must be re-run by hand whenever `build.md` §4.5 is edited.

- **Deferred, on the record.** This major does *not* spend itself on the three fields
  [AGENTS.md](AGENTS.md) §3 parks behind one: `staleness`, `meta.tradeoffs[]` and `meta.others` stay
  **emptied, not removed**, so nothing reading them breaks and a later major can still drop them.
- **Known issue — `clone_ds.py` and null token values.** A design system whose `$value`s are `null`
  clones with a `✓` while both resolvers silently drop the dead tokens, leaving a render that falls
  back to shell defaults and looks plausible. Measured on a real DS export (68 tokens). Unowned; see
  [DESIGN.md](DESIGN.md).

## [1.11.1] — 2026-09-19

*P0 render fix. A real project at scale rendered **blank on both routes** under v1.11.0; the cause was
one line in `render.py`.*

### Fixed
- **`render.py` no longer blanket-escapes `</` in render bodies.** `_escape_body` used to rewrite every
  `</` → `<\/`. That is correct for the one sequence that can end a `<script>` element — the literal
  `</script` — but it also hit the JS **regex literal `/</g`**, the standard HTML-escape idiom
  `.replace(/</g, '&lt;')`, turning it into `/<\/g`: an unterminated regex that killed the entire inline
  script (`Uncaught SyntaxError: Invalid regular expression`). A project with 17 such bodies showed a
  blank prototype **and** a blank design-system site. The escape is now **narrow** — `</script` only,
  case-insensitive, word-bounded — which is what the HTML spec requires and what a JS body can tolerate.
  Both render targets share the fix (`_render_fn_bodies`). The `json.dumps` escapes for the inlined
  registry and node JSON are unchanged: `\/` is a valid JSON escape and JSON has no regex literals.
- New regression guard **`tests/render_escape.py`**: the unit probe (`/</g` untouched, `</script`
  escaped in any case), both targets rendered with a `/</g` body and a literal `</script>` string
  (closer count must equal the shell's), and — when `node` is on PATH — a syntax check of the emitted
  script plus a negative control proving the old blanket escape fails it.

### Notes
- `lint_registry.py`'s `R-SCRIPT` still flags a literal `</script` in a body (belt and suspenders).
- Discovered by serving a real project through the shipped tools rather than a fixture; that project had
  been running on a hand-patched plugin copy with exactly this narrow escape, so upstream never saw it.

## [1.11.0] — 2026-07-24

*One registry, two sites. `registry.json` now projects into a 4-tab prototype **and** a live design-system site — both deterministic renders, both served by one `/pb:preview`. The UI Design tab is retired.*

### Added
- **Design-system site (`design-system.html`, served at `/design-system`).** A component workbench that
  auto-collects **every** registry component, grouped `scope` → atomic `level`. Each component gets a
  **variant grid** (cartesian product over its enum properties) and — when **interactive** — a **live
  clickable demo**. Interactivity is auto-detected by keyword: a `state` property *or* body wiring
  (`data-action`/`data-nav`/`onclick`/`<button>`/`<input>`/…). Token foundations render as swatches.
- **Push to Figma, per component.** Each component carries its DS Bridge node JSON (pre-computed by
  `registry_to_figma.build_component_nodes`) in a copy dialog — paste into the plugin's *Code → Figma* tab.
  Unresolved DS keys are honest gaps, never invented.
- **Shared runtime (`pb/template/runtime.js`).** The render/interaction helper set is single-sourced and
  injected into the design-system site; a drift-guard test keeps it in sync with the prototype shell.
- **Second render target.** `render.py --ds` + `render.build_ds()` render the design-system site;
  `serve.py` serves **both** routes from the one registry and live-reloads both on any registry/body/token
  edit. `tests/r5_ds_site.py` is the new acceptance.

### Changed
- **`/pb:preview` and `/pb:build --render` build/serve both sites.** One server, two routes (a header
  switcher **Prototype | Design system**); `--render`/`--write` emit both HTML files. ~0 model tokens —
  a second deterministic Python projection of the same registry.
- **`/pb:preview-ds`** now focuses the `/design-system` route of the live server (registry-driven),
  superseding the old `ds_serve.py` clone browser (which read the upstream `.source.json` snapshot).

### Removed
- **UI Design tab.** The prototype shell is now **4 tabs** (Prototype · Project Summary · UX Design ·
  Data). Its live-component role moves to the design-system site — components are never duplicated across
  the two. `.source.json` remains only for `/pb:check-drift`.

## [1.10.0] — 2026-07-19

*UI Design tab reworked into a Figma-style inspector — master-detail, redline anatomy/spec, a box model, and an inline component playground.*

### Changed
- **Prototype tab — full-bleed device preview.** Removed the tab title and page padding so the device
  frame fills edge-to-edge; added an app favicon (brand initial) and dropped the non-functional new-tab
  button from the browser chrome.
- **UI Design — master-detail layout.** Replaced the component card grid with a MUI-docs-style split: a
  scrollable name list (Global / Local / Screens) on the left, the selected component's detail stacked on
  the right — inline **component playground → Anatomy → Specification → Layer properties → UI Logic →
  Usage** (no per-section tab switcher).

### Added
- **Anatomy redlines.** Auto-extracted, numbered element callouts placed *outside* the component with
  single straight leaders (no corners), a fixed **Left → Right → Top → Bottom** side priority, gutters
  that hug the component so leaders stay short, and a dashed bounding-box outline for the container part.
  Every badge clears the object and box edges by ≥24px; the token list per element is typed (swatch +
  name + value).
- **Specification redlines — consistent across components.** Width dimension spans the component's outer
  box; element heights run down the left and inter-element gaps down the right (both anchored to the outer
  edge); uniform padding collapses to one chip and never overlaps content. Plain-pixel labels.
- **Layer properties — box model.** A Figma-style nested **Margin → Border → Padding → content W×H**
  diagram, measured live from the component, with a value chip per side (`–` for zero).
- **Component information — inspect list.** Variant props render as diamond-marked selects, free-text props
  as `Aa` fields — one labeled row each, all live.
- **Component playground (inline).** A preview canvas with a light/dark canvas toggle beside a controls
  panel (component props + Display / Color Mode + reset), rendered inline at the top of the detail.

## [1.9.0] — 2026-07-18

*Shell UI: the Prototype header tools collapse into one **Sandbox** control in the meta nav.*

### Changed
- **Consolidated Sandbox menu.** The per-tab Prototype header tools (Browser/App chrome toggle, device
  switcher, structure-tree toggle, sandbox ⋯ menu) **plus** the shell version move into a single
  **`Sandbox ▾`** button at the right end of the meta nav, present on all 5 tabs. Clicking it opens one
  popover:
  - **Preview** (Prototype tab only): Chrome · Device (segmented tab group, soft active token) · Structure tree.
  - **Sandbox**: Reset session (top) · Roles · Explore · Terminal testing — Roles/Explore/Terminal are
    dropdowns, disabled when the project has no data for them.
  - **Footer**: `pb v<version>` (moved out of the nav).
  On the other four tabs the menu shows just the Sandbox group + version. Reuses the shell's existing
  `.proto-shell-toggle` / `.proto-device-btn` / popover components — no new visual language.
- Tests updated to the new UI (`shell_version`, `e2e_smoke`, `test_sandbox`): version reads from the menu
  footer; roles are a dropdown; the trigger is the nav `Sandbox` button.

## [1.8.1] — 2026-07-18

### Fixed
- **Tool CLI consistency.** `clone_ds.py` and `resolve_frame.py` now accept the registry path
  **positionally** (`… --from EXPORT registry.json`), not only via `--registry`. The command docs
  (`/pb:pull-ds`, `/pb:check-drift` §5, `/pb:init --figma`) already invoked them positionally, so
  those steps would have errored at runtime. `--registry` still works as an alias. Guarded by
  `tests/tool_cli.py`.

## [1.8.0] — 2026-07-18

*R3 "Figma-frame entry": a second entry door — a project can be born from a Figma frame, not just a
PRD. Schema bumps to **7** (additive migration 0005). DS fidelity is held at entry: layers map to
components that already exist; unmapped layers are logged, never invented. Built + verified fixture-driven.*

### Added
- **`/pb:init --figma <frame>` + `pb/tools/resolve_frame.py` + the `ref-figma-frame` skill.** Read a
  Figma frame via the Figma MCP, normalize it to a **frame-export**, then deterministically map each
  layer to a known DS component — emitting a registry **screen patch** (elements → `orgId`). Sets
  `meta.entry = "figma"`.
- **`gaps.md` logging.** Every layer with no confident DS match becomes a **labeled placeholder**
  element AND a `gaps.md` entry — pb never invents a component to fill a gap. Resolve each by
  cloning/adding the component and re-resolving, or building it with `/pb:build`.
- **`tests/r3_figma_entry.py` + `fixtures/frame-export.json`.** The R3 acceptance end-to-end
  (frame → screen patch with `orgId`s ⊆ known components + unmapped layers in `gaps.md`), asserting DS
  fidelity: nothing invented, nothing silently dropped.

### Changed
- **Schema 6 → 7** via additive migration `0005_entry` (adds `meta.entry` = `"prd"` | `"figma"`, default
  `"prd"`). Registry template + golden carry it; `/pb:update-version` migrates cleanly (up→down reversible).

## [1.7.0] — 2026-07-18

*R2 "export tiers": the prototype can now emit code, not just HTML — at a tier that matches the
need. Schema bumps to **6** (additive migration 0004). The scaffold tier is built + verified
fixture-driven; the **hardened tier is deferred** (see below).*

### Added
- **`/pb:handoff-dev --tier=host|scaffold|hardened` [`--component <id>`].** Tiered engineering
  hand-off, contract-gated (fail-closed `lint_registry.py --strict`) first.
- **Scaffold tier — `pb/tools/render_react.py` + the `design-component-export` skill.** Deterministic
  registry → a self-contained **React + Vite** app: one wrapper component per registry component/screen
  (reusing its render body), `tokens.css` (`:root` vars) + a token-mapped `tailwind.config.js`, and
  `npm run dev` scaffolding. Runs and lints clean. Fulfils the long-backlogged JSX/TSX export at the
  scaffold level (NS9).
- **`tests/r2_export_tiers.py`.** The R2 acceptance: migration 0004 reversibility + the scaffold
  emits a runnable React app (valid wrappers, resolvable imports, token CSS + Tailwind theme) from the
  golden fixture, and `--component` exports a single subset.

### Changed
- **Schema 5 → 6** via additive migration `0004_export_tier` (adds `meta.outputTier` default `"host"` +
  `meta.exportTarget` null). Registry template + golden fixture carry the fields; `/pb:update-version`
  migrates cleanly (up→down reversible).
- `host` tier delegates to `/pb:validate` (unchanged behavior, now named as a tier).

### Deferred (not built — inputs missing)
- **Hardened tier** (`harden_export.py`, `design-component-harden`, `pb-hardener`): idiomatic,
  DS-integrated per-component JSX, MCP-resolved + repo-matched + `validate_code`-scored + reviewed.
  `/pb:handoff-dev --tier=hardened` **stops with a clear message** — it needs the G-B decision (target
  repo AntD vs Tailwind), `pb-full-picture.md`'s export contracts, and the DS-MCP resolution path. No
  fake idiomatic export is emitted.

## [1.6.0] — 2026-07-18

*R1 "DS truth": the design system becomes a **cloned, verifiable source** rather than a loose
label. Schema bumps to **5** (additive migration 0003). Built and verified fixture-driven — no
production DS required.*

### Added
- **`/pb:pull-ds` + `pb/tools/clone_ds.py` + the `ref-design-system` skill.** Clone a DS via the
  fallback ladder — a dedicated **DS MCP** → a **Figma design-system link** → the **current code
  library** → a **common DS** — normalized to one DS-export, then materialized deterministically:
  tokens merged into `registry.json` (additive), `design-system/<name>/<name>.md` (scannable
  reference) + `design-system/<name>/.source.json` (drift snapshot) written, and `meta.dsSource` +
  `meta.platform` recorded. `clone_ds.py --drift` compares a fresh source export against the snapshot.
- **`/pb:preview-ds` + `pb/tools/ds_serve.py`.** A storybook-style server for the cloned DS — token
  foundations as visual swatches + the component catalog. Read-only; re-reads on every refresh.
- **`/pb:init` clone step.** The DS Lock now captures `platform` + the clone source (the ladder) and
  offers to run `/pb:pull-ds`; seeds `meta.platform`, leaves `meta.dsSource` null until cloned.
- **`tests/r1_ds_truth.py` + `fixtures/ds-export.json`.** The R1 acceptance end-to-end
  (clone → `preview-ds` → change one token at source → `check-drift` reports drift), fixture-driven.

### Changed
- **`/pb:check-drift`** gains §5 — a read-only, advisory **DS-drift audit**: re-resolve the source and
  diff it against `.source.json`. Never blocks. `/pb:handoff-close` runs it as an advisory pre-flight.
- **Schema 4 → 5** via additive migration `0003_ds_source` (adds `meta.platform` default `"web"` +
  `meta.dsSource` null). Registry template + golden fixture carry the fields; `/pb:update-version`
  migrates old projects cleanly (up→down reversible).

## [1.5.1] — 2026-07-18

*R0 groundwork: hygiene + safety so pb can sit cleanly inside a real repo. Command renames all
ship backward-compat aliases; nothing existing breaks. Schema stays v4 — no migration.*

### Added
- **`/pb:snapshot` + `pb/tools/snapshot.py`** — pb's history model: timestamped `registry.json`
  copies under `<project>/history/` (`--list` / `--restore`, with an auto-snapshot before every
  restore). Pure stdlib; it **never** branches and **never** touches the host repo's git — the
  reason snapshot (not an orphan branch) was chosen for adopt-in-place.
- **`/pb:init` adopt-in-place mode** — inside an existing git repo, pb sidecars everything under
  `.prototype/`, appends a pb block to the host `.gitignore`, and records a **read-only-outside**
  Principle in `constitution.md` (pb never edits host-repo files). `--adopt` / `--standalone` force it.
- **`pb/template/AGENTS.template.md`** — a recipient-facing orientation now written into every
  `/pb:handoff-close` (what the folder is, that `prototype.html` is derived, how to continue from `bundle/`).
- **`AGENTS.md`** (repo root) — build guardrails for anyone (human or agent) working on pb.
- **`tests/r0_hygiene.py`** — guards the R0 renames, alias resolution, the `check.py` shim, and the
  snapshot round-trip.

### Changed
- **Command renames (aliases kept):** `/pb:sync-flow` → **`/pb:flow`**, `/pb:sync-erd` →
  **`/pb:data`**, `/pb:hand-off` → **`/pb:handoff-close`**. The old command files are thin redirect
  stubs that still resolve.
- **`/pb:handoff-close`** now closes out into a single **`handoff/`** folder: a view-only
  `prototype.html` + a portable `bundle/` (ingestible by `/pb:init --import handoff/bundle`) + a
  generated `AGENTS.md`. `--people` / `--context` narrow to one piece.
- **Contract validator renamed** `pb/tools/check.py` → **`pb/tools/lint_registry.py`**; `check.py`
  stays as a compatibility shim (both `import check` and the CLI keep working).

### Deprecated
- `/pb:sync-flow`, `/pb:sync-erd`, `/pb:hand-off` command names and the `check.py` tool name — all
  kept working via alias/shim; scheduled for removal in a future major release.

## [1.5.0] — 2026-07-15

*Agent-powered testing sandbox, a multi-agent orchestrator, role-gated prototypes, and an ⌥-hover
element inspector. Every registry addition is optional/additive — schema stays v4, no migration; a
project without them behaves exactly as before. (Subsumes the terminology rename in [Unreleased].)*

### Added
- **Sandbox testing — `/pb:test`.** A Playwright-backed runner (`pb/tools/test_run.py`) drives the
  prototype's `data-*` runtime to verify authored scenarios: `--functional` (runs
  `flow.stories[].scenarios[].test` blocks and writes `lastResult` → live ✓/✗/○/☐ glyphs in the UX
  Design tab), `--roles`, `--server` (reachability), `--explore`. `--security` runs
  `pb/tools/security_scan.py` (stdlib secrets + PII scan). Playwright is the one optional dependency,
  isolated to this path like Node/npm at `/pb:validate`, and degrades gracefully if absent.
- **Multi-agent orchestration — `/pb:orchestrate`, `/pb:explore`.** Eight `pb-*` subagents
  (`pb/agents/`) + a stdlib wave scheduler (`pb/tools/orchestrate.py`) + an idempotent installer
  (`pb/tools/agents_install.py`). `/pb:plan` tasks now carry `agent` / `deps` / `slice`;
  `/pb:orchestrate` dispatches them in dependency **waves** (serial registry writes, render once per
  wave, acceptance-gated by `pb-tester` + `pb-reviewer`). `/pb:explore` fans out N `pb-builder`
  agents for parallel design options to compare and keep one.
- **Role-gated prototypes.** `meta.roles` / `meta.defaultRole` / `screens[].roles` + element
  `data-roles` gate the Prototype tab (an `isAdmin` role bypasses). A sandbox menu (hourglass icon)
  with a radio role list (each role's abilities / JTBD) + a Reset row rides the header; the role
  switcher + Reset stay visible to viewers even in a `--people` hand-off (only authoring controls hide).
- **Inspect mode.** Hold ⌥/Option and hover the live preview to see an element's structured id path
  (`screen › element › component`); ⌥-click copies it to paste to the AI. Best-effort derivation from
  the DOM's existing identity (`data-handoff-el` → registry label + component; else an anatomy part; else a fallback).

### Fixed
- `check.py` no longer crashes on a string (prose) `anatomy` — the `--strict` gate works on such projects.
- `orchestrate.py --json` always emits a parseable object, including IO / usage / invalid-UTF-8 error paths.
- `test_run.py` fails closed (exit 2) on server-boot failure and invalid-UTF-8 input instead of a traceback.
- `security_scan.py` handles deeply-nested JSON (RecursionError) and non-UTF-8 input cleanly.
- `--roles` leak detection now covers `display:contents`, `visibility`, and text-node-only children.

### Changed
- Reintroduces the regression suite (`tests/`) + fixtures (`golden`, `security_bad`, `violations.json`)
  consolidated into the plugin repo, and adds `test_sandbox` / `test_inspect` / `test_orchestrate` /
  `test_security` / `test_agents_install`. Version bumped to **1.5.0**.

## [Unreleased]

### Rename "migration" → "version update" — 2026-06-25

*User-facing terminology change. The `/pb:migrate` command is renamed to `/pb:update-version`, and
all docs + command prose now say "version update" / "update the version" instead of "migration" /
"migrate". No behavior change — the engine, its rules, and the registry contract are untouched.*

- Command `/pb:migrate` → **`/pb:update-version`** (`pb/commands/migrate.md` → `update-version.md`).
- Doc `docs/migrations.md` → **`docs/version-updates.md`**.
- Runner output banners reworded ("Version update plan / complete / failed …"); shell command hints
  (`pb/template/prototype.html`) and the `plugin.json` description updated.
- **Engine preserved.** Internal module/file names (`pb/migrations/`, `manifest.py`,
  `migrate_runner.py`, the `000N_*` steps), function names, and `registry.json`'s `schemaVersion` key
  are intentionally kept — no import, invocation path, or stored registry breaks. The version-update
  command and its rules are fully intact.
- Released changelog sections below are left as the historical record (they shipped under the old
  `/pb:migrate` name).

### Remove the test suite + CI — 2026-06-25

*Repo-cleanup: the regression suite and the CI workflow that ran it are removed. No
user-facing change — these were dev/CI-only and never shipped in the plugin (`./pb`).*

- Deleted `tests/` (shell-lint, skill-refs-lint, render-budget, check-violations, e2e-smoke,
  shell-version) and the committed `fixtures/` (golden registry + render bodies, violations.json).
- Deleted the version-update selftest (`pb/migrations/selftest.py` + `pb/migrations/_selftest/`).
  The runtime version-update engine (`manifest.py`, `migrate_runner.py`, the `000N_*` steps) is unchanged.
- Removed `.github/workflows/ci.yml`. The release/CD workflow (`release.yml`) is unchanged.
- `docs/version-updates.md` "Authoring a version update" now verifies via `/pb:update-version` dry-run
  instead of the deleted selftest.
### Force reuse of nested global components — 2026-06-25 (v1.4.3)

*Hand-off + validator feature. Schema-stable (4) — no migration required.*

- **`anatomy.parts[].orgId`** — a component anatomy part that IS a reused global (`badge`, `button`, …)
  now declares it via `orgId`, mirroring `screens[].elements[].orgId`. Makes nested reuse explicit and
  machine-checkable (the hand-off can't infer it from render code).
- **`/pb:build-figma-handoff`** — Step 6 now branches on `part.orgId`: a declared nested global is
  inserted as an **instance** of its `dsMatch.componentKey` (per parent variant) and recorded under
  `figma-transfer.components[<parent>].nestedInstances[<orgId>]`, never redrawn locally. New **G-FP6
  invariant #7** ("nested globals = instances") + a NEVER rule enforce it.
- **`tools/check.py`** — new rules: **R-NEST** (a part `orgId` must resolve + be `scope:global`),
  **R-NEST-HINT** (warns on a part that looks like a global but declares no `orgId` — drift detector),
  and a **`--figma` mode** (`check.py --figma registry.json figma-transfer.json` → **R-NEST-FIGMA**)
  that verifies every declared nesting has a recorded instance whose key matches the global's DS match.
  Runs offline over the two committed contracts, so CI asserts it without the Figma plugin.

### CI/CD + security hardening — 2026-06-19

*Infrastructure only — no user-facing changes, no schema bump, no migration required.*

**CI fixes (`.github/workflows/ci.yml`)**
- Push trigger restricted to `main`; PRs cover feature branches — eliminates the double-run on open PRs (was `branches: ["**"]`).
- Concurrency group fixed to `head_ref || ref` so runs from the same PR branch collapse correctly.
- Runner pinned to `ubuntu-24.04` (was `ubuntu-latest`; drifts on image updates).
- Playwright pinned to `1.60.0` (was floating `pip install playwright`). Version defined once at job level so the browser-cache key and the install pin stay in sync.
- Playwright Chromium browser cache added (keyed on OS + version).

What the CI suite checks (budget: wall-clock ≤ 6 min, no release ships red):

`unit` job (Python, stdlib-only):
- Migrations selftest — schema migration logic is internally consistent
- Shell hygiene lint — no duplicate steps, no dead code, no v0.4 strings
- Skill-reference lint — no dangling skill refs, commands are portable
- Render determinism — golden registry rendered twice, SHA-256 of both outputs must match
- Render-time budget — full render of 50 components / 20 screens must complete in ≤ 100 ms
- `check.py --strict` clean on the golden — registry passes all structural + naming-contract checks
- `check.py` catches every seeded violation — the validator rejects all known bad patterns

`e2e` job (Playwright Chromium, dev/CI-only, never shipped):
- Browser smoke across all 5 tabs: Prototype, UI Design, UX Design, Data, Project Summary
- Validates: token rendering, form validation, tab navigation, view-only hand-off mode, zero console errors

**CD: GitHub Release on version tag (`.github/workflows/release.yml`)**
- New workflow fires on `v*` tags only (the tag push is the human approval gate).
- Verifies the pushed tag matches `plugin.json` version before creating the release — a mismatched tag fails loud.
- Uses `gh release create --generate-notes --verify-tag` (no third-party action).

**Plugin publishing (`.claude-plugin/`)**
- `plugin.json` created (was missing; required for the release version-coherence check). Version `1.4.2`, name `pb`.
- `marketplace.json` unchanged — was already correct.
- README install section updated: GitHub-based remote install (`/plugin marketplace add danhnbui/prototype-builder`) added as the primary path; local install kept as a development option.

**Security: CodeQL alert remediation (`pb/tools/serve.py`)**
- CWE-22 path traversal (High, ×3): `serve_static` now uses `relative_to()` inside a try/except (raises `ValueError` on traversal) followed by a path rebuild from `root` — fully breaks the taint chain from user input. CodeQL did not recognize the previous `is_relative_to()` boolean guard.
- CWE-113 HTTP response splitting (Medium, ×1): `_send` strips `\r` and `\n` from the `Content-Type` header value before writing.
- Server was already bound to `127.0.0.1` by default; no change needed.

## [1.4.2] — 2026-06-16

### Shell version coherence — stamping + drift detection

*The rendered shell now carries the plugin version everywhere it's served or produced, so a stale render
can't hide silently. Advisory only — nothing blocks a build or preview.*

**Version-stamped shell**
- `render.py` reads the plugin SemVer from `pb/.claude-plugin/plugin.json` and fills a new
  `{{PB_SHELL_VERSION}}` placeholder — driving a small `pb vX.Y.Z` badge in the meta-nav corner.
- `render_file` (and `serve.py --write`) write a `<!-- pb-shell vX.Y.Z · rendered <ISO-8601> -->` stamp near
  the top of `prototype.html`. `build_html` stays pure/deterministic: the timestamp lives only on the disk
  artifact, never the in-memory preview.
- `/pb:preview`'s startup banner shows the rendering version (`· pb vX.Y.Z`).
- A bad/unreadable `plugin.json` degrades to `pb vunknown` rather than crashing a render.

**Drift detection (advisory, read-only)**
- `/pb:check-drift` gains a **shell-coherence** step: it compares `prototype.html`'s stamp to the installed
  plugin version and warns on a mismatch (`⚠ Shell drift…`) or a missing stamp — **never blocks**, never writes.

**Upgrade guide**
- New `docs/upgrading.md` — the **three-layer model** (plugin code · registry schema · rendered output), the
  canonical upgrade sequence, the author dev-loop, and a symptom → layer → fix table. Linked from the README;
  the matching "shell-drift detection" non-goal retired from `docs/migrations.md`.

**Schema:** unchanged (`CURRENT_SCHEMA = 4`) — no migration required.

## [1.4.1] — 2026-06-10

### v1.4 refit — quality, governance, portability

*Safety net + governance + the strategic move of render bodies out of JSON into real files, + shell
hygiene + portability. The audit harness is now the permanent regression suite.*

**Safety net (Phase 0)**
- **No release ships red.** `.github/workflows/ci.yml`: a `unit` job (migrations selftest · golden render
  twice → identical SHA-256 · render-time budget · `check.py --strict` clean on golden · all seeded
  violations caught · shell hygiene lint) and an `e2e` job (Playwright chromium smoke). Fixtures committed
  under `fixtures/`; tests under `tests/`.
- **Backup-collision bug fixed.** `migrate_runner.py` no longer overwrites a backup on a same-second
  re-apply (appends `-2`, `-3`, …; `_latest_backup` sorts by mtime).
- **Friendly render errors.** `render.py` reports invalid JSON / missing files in one line, exit 2, no traceback.

**Governance (Phase 1)**
- **The contract is machine-checked.** New `pb/tools/check.py` (stdlib) validates shape, kebab/unique ids,
  the `renderFn` naming contract, `orgId` resolution, token `kind`, a `</script>` page-killer (error), raw
  hex/px (warn; `--strict` → error), the runtime-required `danger` token, and flow/erd shape. Wired
  advisory into `/pb:build` and **fail-closed** (`--strict`) before `/pb:hand-off` and `/pb:validate`.
- **Out-of-box danger gap closed.** The template seeds a `danger` token and the shell `:root` carries a
  `--danger` fallback, so a fresh project's validation border is red with zero manual token work.
- **`pbEscape` hardened** to escape `"` and `'` (names with quotes are safe in attributes/handlers).

**Render bodies are real files (Phase 2, schema 3 → 4)**
- Each component/screen carries a `renderSrc` → `render/components/<id>.js` / `render/screens/<id>.js`;
  `render.py` reads and compiles them. Lintable, diffable, no triple-escaping. **Measured:** the golden
  registry's resident state shrank **28.3%** (16,036 → 11,497 bytes); render holds at **0.7 ms** @ 50/20.
- Migration `0002_v13_to_v14` extracts/re-inlines bodies and is exactly reversible (selftest round-trip).
- **Page-killer eliminated.** All emitted bodies pass a `</` → `<\/` escape (a `</script>` body now boots).
- `serve.py` watches `render/**/*.js`; `/pb:build`, `/pb:hand-off --context`, `/pb:init --import`,
  `check-drift`, and the Figma token scan all account for the body files.

**Shell hygiene + honest contracts (Phase 3)**
- **`CHAT_PROMPTS` deduped + rewritten** against the real `/pb:*` command set; removed v0.4
  `agent-skill-set` / `USER-FLOW-GUIDE` references.
- **Dead wireflow feature deleted** (D2) — `WIREFLOW_SCREENS`/`WIREFLOW_NOTES`/`wfCardHtml` and their CSS;
  `node/status/preview` stripped from `sync-flow.md` + the playbook so command demands match the renderer 1:1.
- **View-only leak fixed** — `/pb:hand-off --people` hides every authoring CTA (sync bars, Figma panel,
  empty-state actions); unpopulated tabs render a neutral "Not included in this hand-off."
- **Truthful shell header** (no `cp template.html`, correct tab names, "do not hand-edit"); stale
  `plugin.json 1.2.0` reference in `docs/architecture.md` corrected to 1.4.0.

**Schema:** `CURRENT_SCHEMA = 4` — run `/pb:migrate` to upgrade an older registry.

## [1.4.0] — 2026-06-10

A major redesign of the prototype shell — every tab now shares one unified, two-column layout — together
with the schema-migration system. Template + docs + commands; the registry contract gains several
**optional, tolerated-absent** fields (schema stays at **3**, no migration required).

### Added — unified UI shell (`pb/template/prototype.html`)
- **One page chrome for every tab** — a `pb-page-header` (title + a `?` **info dialog** documenting the
  tab's commands/skills + an optional CTA) over a `pb-content` shell: `--full` (Project Summary) or
  `--split` (left main · right aside, **320–400px**). Replaces the old `meta-tag`/`meta-sub` headers.
- **Empty-states everywhere** — an unpopulated tab renders only the header + an empty-state card that owns
  the CTA; no dead controls against empty data.
- **Prototype** — a device-framed preview (browser chrome on desktop, bezel + notch on tablet/mobile; sizes
  not in `meta.devices` are disabled) plus a screen → component **structure tree** aside.
- **UX Design** — the flow canvas (multi-flow dropdown + legend) on the left; **screen-size W×H** inputs and
  **User stories | Test cases** on the right. Test cases are authored as **QA** across five lenses
  (UX · UI · Function · Business · System-edge), with a **Coverage gaps** callout for edges the flow misses.
- **UI Design** — a **Global | Local | Screen** control + a **design-system bar** (name + design link +
  code-library link, or an "add one" affordance). Components list by `scope`, **grouped by atomic `level`**;
  clicking a component/element opens its full spec in the persistent aside. The **Push to Figma** panel now
  shows a **reuse** badge for DS-matched components and **which screens each push affects**.
- **Data** — the ERD diagram in the shared canvas wrapper + an entity legend / click-to-inspect aside with a
  **mock-data viewer** (preview Typical / Empty / Long-value sample sets against the fields).

### Added — registry contract (all optional / tolerated-absent)
- `meta.designSystem { name, designLink, codeLibrary, linked }`, `meta.devices[]`, `components[].level`
  (`atom|molecule|organism`), `flow.screen {w,h}`, `flow.flows[]`, `flow.coverageWarnings[]`, `erd.mock[]`
  — documented in `prototype-builder.md`.
- **Atomic-design principle** — constitution principle 5 + design-system rule **R0.5**; the UI groups the
  component lists by level.

### Changed — commands + docs
- `/pb:init` seeds `meta.designSystem` (from the DS Lock) + `meta.devices`.
- `/pb:build-check-design-system` tags each component's atomic `level`.
- `/pb:sync-flow` authors QA-lens test cases + `flow.coverageWarnings`, and persists `flow.screen`.
- `/pb:sync-erd` gains `--mock` to generate `erd.mock[]` edge-case sets.
- `/pb:build-figma-handoff` G-FP2 surfaces affected screens per updated component; Step 6 reports progress.
- `CLAUDE.md` tab-render section and `README.md` updated to the v1.4 UI.

### Added — schema migration system
- **One preview per project** (`pb/tools/preview_register.py`, `/pb:preview`): each project has a single
  preview source of truth — the live `/pb:preview` server over its `registry.json`; `prototype.html` is a
  derived hand-off snapshot, not a parallel preview. When an in-app preview pane is used, the new helper
  keeps exactly **one** canonical `.claude/launch.json` entry per project (`pb-preview · <folder>`):
  upsert in place, dedupe entries for that project, never touch entries it doesn't own. Stdlib-only.
- **`/pb:migrate`** — versioned schema migration command: dry-run (default), `--apply`, `--rollback`,
  `--to <N>`, `--registry <path>`. Backup-first, single-write, render-validated. Stdlib-only.
- **Migration framework** (`pb/migrations/manifest.py`, `pb/migrations/migrate_runner.py`): `CURRENT_SCHEMA`
  as the single version source; `chain(from_v, to_v)` helper; module contract (`up`, `down`, `describe`,
  `memory_notes`). Advisory memory rule: migrations never auto-edit `constitution.md`.
- **Soft compat gate** on write-path commands (`/pb:build`, `/pb:sync-flow`, `/pb:sync-erd`,
  `/pb:init --import`): prints a one-line schema-gap banner and suggests `/pb:migrate`; hard-stops only
  when the pending write touches a slice a pending migration changes.
- **`registry.template.json`** now carries `meta.schemaVersion: 3` and `meta.device: "desktop"` so fresh
  scaffolds are correctly stamped.

### Migrations
- `CURRENT_SCHEMA = 3` (first formal stamp; unstamped registries treated as schema 2).
- Migration `0001_v12_to_v13`: "v1.2 → v1.3: add meta.device, components[].scope, structured flow/erd shape (legacy html preserved)."

## [1.3.1] — 2026-06-07

Docs / packaging cleanup for publishing — no code or command changes.

### Removed
- `docs/v0.4.0/` (SpecKit-era SRS / architecture / orchestrator / execution-plan), `docs/CHANGES-from-v0.4.0.md` (superseded by this changelog), and `docs/code-to-figma-handoff-research-brief.md` (research now implemented as the `/pb:build-figma-handoff` G-FP gates) — all retained in git history.
- Leftover root `design-system/` starter — a per-project artifact regenerated by `/pb:init`, never a shipped plugin asset.

### Changed
- Bumped `docs/architecture.md` + `docs/data-flow.md` version refs to v1.3.

## [1.3.0] — 2026-06-07

A render-layer redesign: every tab in the shell (`pb/template/prototype.html`) gets richer, and the
prototype itself becomes a real, clickable flow. Data-only change to the registry contract — same generator,
no new dependencies.

### Added
- **Interactive prototype runtime** — the Prototype tab is now a live flow driven by `data-*` attributes the
  shell wires up: `data-nav="<screen-id>"` (navigate), `data-action="toggle-password"`, and
  `data-action="submit"` which validates the form (`data-required` · `data-validate="email"` ·
  `data-minlength`) then on success runs `data-go` (navigate) / `data-toast` (toast) /
  `data-redirect`+`data-redirect-ms` (auto-navigate). Clicking links/buttons moves between screens.
- **Icon-only device switcher** replaces the screen-switcher: desktop (≤1180px) / tablet (834px) /
  mobile (390px), one viewport with internal scroll. The default comes from a new registry field
  **`meta.device`** (`'desktop'|'tablet'|'mobile'`), seeded at `/pb:init`.
- **State-variant component demos** — if a component declares a `state` property (`properties[]` entry
  `id:'state'`), the UI Design demo renders one labeled variant per state. Interactive components MUST ship
  their states this way (e.g. default / error / disabled).
- **UI Design Global | Local sub-tabs** — components split by `components[].scope` (`'global'` when
  `scope==='global'` or a `dsMatch` exists, else `'local'`), via the shared `meta-subtab` component.
- **Data Diagram | Table toggle** — Diagram = the `erDiagram`; Table = one styled `<table>` per entity (a
  real table component, not text alignment) built from a new structured `erd.table[]`
  (`{entity, field, type, example, notes}`).

### Changed
- **Unified `meta-subtab`** — the Project Summary tab now uses the same sub-tab component as UI Design.
- **UX Design renders from structured data**, not a pre-baked HTML blob: `flow.mermaid` + `flow.stories[]`
  (`{title, priority, jtbd, path, scenarios[], …}`). The left sidebar now has two sub-tabs — **User stories** |
  **Test cases** — both built from `flow.stories[]`. Mermaid uses `curve:'basis'` (smooth curved connectors,
  not zig-zag step), classDef colors match the on-canvas legend palette (start/end zinc · decision sky ·
  action lavender · input pink · subprocess purple), and a legend is shown.
- Registry contract extended (data-only): `meta.device`, `components[].scope`, the `state` property
  convention, the screen `data-*` interaction runtime, and structured `flow`/`erd` shapes
  (`flow.{mermaid,stories[]}`, `erd.{table[],mermaid}`); each tab's `html` field is now a legacy fallback only.

## [1.2.0] — 2026-06-06

### Added
- **Preview dev server** (`pb/tools/serve.py`, `/pb:preview`): watches `registry.json` (+ the shell
  template + `render.py`) and live-reloads the browser on every change over Server-Sent Events. Renders
  **in memory** through the same generator as `/pb:build --render` (so the preview is byte-identical and
  costs ~0 model tokens), never clobbering the on-disk `prototype.html`. `--write` opts into also keeping
  `prototype.html` fresh; a bad registry mid-edit shows a recoverable error page instead of crashing.
  Stdlib-only — no new dependencies.
- Figma hand-off render audit (**G-FP6**): a mandatory, machine-checkable read-back after the push —
  auto-layout on every frame · 0 absolute children · 0 raw values (color/space/radius all bound to
  variables) · variants in a ComponentSet · screen elements as instances · bound-token count ≥ the
  G-FP3 union. A failing invariant HARD-FAILs and **blocks the Step 7 contract write-back**, so a
  hand-off is "done" only when the pushed result verifies — making the gated process the enforced
  path, not merely the recommended one.

### Changed
- `render.py` refactored to expose a pure `build_html(reg, shell)` (the single render truth shared by the
  CLI and the dev server) and a `RenderError`; the `render.py` CLI output is unchanged.
- `serve.py` hardened to run under a sandboxed launcher (e.g. a macOS preview pane TCC-blocked from
  `~/Desktop`): resolve all paths to absolute, then `chdir` to an accessible dir so an unreadable inherited
  cwd no longer crashes startup (`os.getcwd()` EPERM); path display + static root are cwd-free. Relative
  and absolute invocations both verified.

## [1.1.1] — 2026-06-05

A standalone, CLAUDE.md-native rebuild of the SpecKit Prototype Builder. A plumbing swap, not a rewrite —
the crown-jewel logic ported unchanged. See [docs/CHANGES-from-v0.4.0.md](docs/CHANGES-from-v0.4.0.md).

### Added
- `registry.json` as the single source of truth for prototype state.
- Deterministic render generator (`pb/tools/render.py`): `registry.json` → `prototype.html` at ~0 model tokens.
- Claude Code **plugin** packaging (`pb@product-builder`); the `/pb:*` command surface (12 commands).
- `/pb:build-check-design-system` — DS-first reuse / variant / build-local + naming contract.
- Two-mode `/pb:hand-off` — `--people` (view-only + cover) and `--context` (portable bundle).
- Memory layer: `memory/constitution.md` (Principles + Stack/DS locks) and `memory/decisions.md`.
- `config` block (`viewOnly`, `cover`, `iconCdn`) for a DS-agnostic, shareable output.

### Changed
- `scaffold` → `init`; `figma-push` → `build-figma-handoff` (DS-neutral).
- Tabs renamed: User Flow → UX Design, Design Handoff → UI Design, ERD → Data.
- Tab-2 (Project Summary) sync folded into `init` / `specify` / `clarify` command bodies (no hooks).
- Design-system-agnostic core: neutral tokens (`--neutral-*`, `--shadow-*`, `--radius-*`), configurable icons.

### Removed
- SpecKit: `extension.yml`, `preset.yml`, the `after_*` hooks, `sync-tab2`, `skills-refresh`.
- All HIVE / PropertyGuru hardcoding.

### Fixed
- Render generator: inline `registry.json` safely (`</` → `<\/`) without double-escaping JSON — fixes any
  registry value containing embedded quotes or newlines (e.g. flow/erd HTML).
- Tab 1 (Prototype) now renders `registry.screens` as the **live interactive app** (with a screen
  switcher for multi-screen prototypes) instead of a hand-edited placeholder — caught by an end-to-end
  self-test build.
- Figma handoff identity: `figma-transfer.template.json` now stores `dsMatch.figmaComponentId` (matching
  what `build-figma-handoff` and the `figma-use` skill read) — the prior `componentId` mismatch would have
  re-created components instead of updating them in place.
- Figma handoff token coverage (G-FP3): collect the **union** of declared tokens + every `var(--…)` used in
  the render bodies, so tokens that are used but not separately declared (spacing, semantic colors, shadows)
  are no longer silently skipped — caught by the dry-run test (3 → 17 tokens on the selftest fixture).

## [0.4.0] — prior baseline (SpecKit Prototype Builder)

The SpecKit preset + extension: a 5-tab single-file `template.html`, `after_*` hooks, and `figma-push`.
Retained, untouched, in its own repo (`spec-kit-extension-prototype-builder`).
