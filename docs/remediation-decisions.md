# Remediation decisions

The why-log for the systematic remediation of Product Builder, measured against Atlas (a live pb
project at real scale — read-only reference, never modified). One entry per decision, newest
first, in the same shape as a project's `memory/decisions.md`. Plan: `~/.claude/plans/…functional-ripple.md`.

Phase A (solution discovery) logs decisions here as each problem is walked through. Phase B
(orchestrated implementation) is planned from this file.

---

## D-28 · The logic contract (schema 11): derived by default, two verbs that earned it, and a lossless migration — 2026-09-19
**Problem:** #1 deep half — the logic contract + runtime verbs
**Decision — the contract.** A sidecar `logic/{components,screens}/<id>.json` referenced by `logicSrc`,
mirroring `specSrc`. **Derived and rewritten every run:** `seam`, `handlers`, `disclosure`.
**Hand-authored and deliberately short:** `writes[]` (which store slices the item mutates) and
`affordances[].why`. Nothing else is authored.
**Decision — the verbs.** Ship **two**, drop **two**, defer **one**:
| Candidate | Retires on the real project | Verdict |
|---|---|---|
| `data-machine` / `data-step` | 4 copies of one 6-state wizard (~63 attrs: bki 18, ecc 16, bev 15, xlx 14) | **ship** |
| `data-preserve` | **24** calls passing a restore-id list (of 41 `pbAppRerender` + 3 KeepingFilters + 17 `pbDrawerRerender`) | **ship** |
| `data-bind` | 24 field-read sites (`pbFieldVal` 18, `pbFieldChecked` 3, `.value` 3) | defer |
| `data-save` | 24 save fns — but the mutation in each is project-specific | **drop** — an attribute cannot express the middle |
| `data-group` / `data-panel` | would replace a `:has()` mechanism with **0** R1/R2 violations across 222 uses | **drop** — a downgrade |
**Decision — `registry.runtime[]`.** Real module files inlined before render bodies, plus declared CDN
dependencies. Retires **3** fake modules — `app-store.js` (1,260 lines / 60 fns), `bulk-excel-engine.js`
(797 / 21), `weight-runtime.js` (510 / 22): **2,567 lines and 103 functions declared as components that
render nothing** — and the hand-injected SheetJS `<script>` in the forked shell.
**Decision — the migration.** `0009` **copies** prose into the sidecar's `notes[]` with a `source`
pointer. `logicNotes` and `uiLogic` are **not deleted, not moved, not one character rewritten** —
which makes `down()` pb's first information-lossless rollback. Proven by `--apply` then `--rollback`
on a copy of the real project, diffed to byte-equality.
**Schema 11 carries three additive things:** `logicSrc`, the `ia` slice ([D-16]), and `registry.runtime[]`.
**Why:** [D-23] applied to verbs — measure what each would actually retire before designing it. Three
of five candidates failed that test. The `:has()` case is the sharpest: W1 measured **0 R1/R2
violations** across 222 uses, so a verb there would replace a working declarative mechanism with a
worse one. And W2 proved the split for the contract: static derivation traces **reads but not writes**
(mutations happen inside store helpers), so `writes[]` is the one thing a human must state.
**Corrections to my own earlier claims, recorded:** `data-preserve` would retire **24** sites, not the
"77" I first reported (that was an occurrence count including comments and the definition). And the
fake-module count is **3**, not the 26 a loose `return ''` grep produced — 23 of those were real
components with an empty-state early return.
**Alternatives rejected:** all five verbs (three fail the test); deleting prose in the migration
(loses the rollback guarantee, and [D-08]/the W1 census showed the prose is dated rationale worth
keeping where it is until a human routes it).
**Affects:** `pb/migrations/0009_*.py` + `manifest.py`, `pb/tools/render.py` (`load_logic`,
`registry.runtime[]` inlining), `pb/template/runtime.js` + the duplicated block in `prototype.html`,
`pb/tools/logic_extract.py`
**Reviewed via:** per-candidate retirement counts measured on the real project; fake-module detection
tightened to render bodies containing nothing but `return ''`

## D-27 · The sandbox learns roles: reset clears it, functional honours `test.roles`, `--server` becomes a modifier — 2026-09-19
**Problem:** #2 role-aware testing
**Decision:** Seven changes to one tool, one shell function and one doc — no new tools:
1. **`pbResetSandbox()` clears `state.activeRole`.** A prerequisite, not a nicety — everything else is
   order-dependent without it.
2. **Functional mode honours `test.roles`** — run each scenario once per declared role, falling back to
   `_default_role_id(reg, roles)` (which already exists and is never called from this path).
3. **`--server` becomes a modifier, not a mode** — it should change *where* the runner connects, which
   is what `test.md:14` already promises.
4. **`--roles` runs scenarios**, not just visibility sampling, and gains **`present`/`absent`** expects
   (presence, **not** visibility — conflating them is what makes the current check noisy; CSS hiding is
   the `:has()` reveal mechanism, a different question).
5. **Exit code 3 = "cannot run"** (no Playwright, no server), so `2` can stay "a scenario failed".
6. **Honour `test.seed`** — the real project authors it on every scenario and the runner discards it.
7. **Correct the three false claims in `pb/commands/test.md`** in the same change.
**Why:** measured in the code and against the real project.
- `run_functional` **never calls `setProtoRole`** — the only calls are inside `run_roles`. So "in the
  starting role" (`test.md:13`) is false; scenarios run as whatever role is already active.
- Mode dispatch is `if explore / elif server / elif roles / else functional` — mutually exclusive. So
  `--server` *replaces* functional mode rather than redirecting it, and `--roles` **runs no scenarios**.
- `pbResetSandbox()` resets `protoScreenId`, `protoHistory`, field inputs and the toast wrap — and
  **not `state.activeRole`**. All scenarios share one page sequentially, so once anything sets a role
  every later scenario inherits it.
- The real project authors **`roles` and `seed` on all three** of its test blocks; the runner reads
  neither, and all three report `pass` — as an unknown role.
- This gap is why that project hand-wrote **`gates/role_affordances.py` (325 lines)**, whose header
  documents exactly this ("`--functional` … CANNOT switch role"; "`--roles` only checks `[data-roles]`
  visibility, which is a different mechanism entirely") and records the cost: a manager-side scenario
  was **deleted** because it asserted manager behaviour while running as `hr`, leaving manager KPI
  scoring with zero automated coverage.
**Alternatives rejected:** upstreaming `role_affordances.py` wholesale (a declarative CASES table is
project-specific; the reusable half is `present`/`absent` on scenarios); making `--roles` a modifier too
(it is a genuinely different report).
**Affects:** `pb/tools/test_run.py`, `pb/template/prototype.html` (`pbResetSandbox`),
`pb/commands/test.md`, `pb/skills/sandbox-test`
**Reviewed via:** `run_functional` / mode dispatch / `pbResetSandbox` read directly; the real project's
three test blocks inspected for ignored fields

## D-26 · The design-system site work is halved: fix what reaches the hand-off, defer what only polishes the page — 2026-09-19
**Problem:** #3, #5 — the DS site at real scale
**Decision — DO NOW (4):**
1. **Lint the mis-typed collection prop.** Warn when a prop's `default` is a collection literal inside a
   string (`'[]'`, `'[{…}]'`), or when an `array`/`object`-typed prop carries a string default.
2. **Example data gets a home.** `spec/<id>.json` gains an optional `usage.example` props object the
   demo prefers over `default`. Sidecar only → **no schema bump**.
3. **Coerce, then diagnose.** Parse an `array`/`object` default as data, fall back to `[]`/`{}`, and when
   a demo still throws render a card naming the component **and the prop** instead of a bare
   `render error: x.map is not a function`.
4. **Couple the theme.** Paint the demo stage from the **project's** surface token, not the site's own
   chrome token.
**Decision — DEFER (4):** lazy mounting above a `LAZY_MIN` threshold, the filter bar, scope→level
subheadings + the dead line, and the `MAX_CELLS` relabel/"Show all". Revisit only with evidence the page
is being opened — and ask the people who would use it, not the code.
**Why:** the user asked what the work actually buys, and the evidence is thin. **The one real project
has never touched this site**: its `template/` holds only `prototype.html` (no DS shell fork), and
nothing in its gates, docs or config references `design-system.html` or the `/design-system` route.
The 11 render failures are **confined to the site** — in the prototype, parents pass real props via
`pbUse`, so `default` never fires. And `properties[].type` has only two consumers: this site, and
`registry_to_figma.py`, which reads **enum props only**. `lint_registry.py` never reads `properties` at
all. **The counter-argument, recorded honestly:** absence of use is weak evidence when first contact is
broken (11 error strings, 64,367 px with no filter, orange-on-near-black in dark mode) — someone may
have opened it once and left. The four kept items are the two whose value is independent of the site
(the lint rule and the example data are **hand-off documentation** — a prop documented as a string when
it takes a list of objects is wrong in the bundle a developer receives) plus the two that make first
contact survivable for a few lines each.
**Sharper diagnosis than W0 recorded:** it is not that `_default_props` "has no notion of arrays". Three
faults stack — the registry **does** have the types (27 `array`, 7 `object`); most collection props are
nonetheless **mis-typed `string` with a `'[]'` default**; `_default_props` passes `default` through
verbatim; and even the correctly-typed `avatar-stack` defaults to a *string* of unquoted-key
pseudo-JSON no parser accepts. There is also nowhere to declare example data — hence item 2.
**Measured:** 17,631 DOM nodes · 64,367 px · 415 variant cells · 65 demo stages · 11 of 133 failing ·
0 filters · 0 lazy mounting · grouping by scope only.
**Alternatives rejected:** the full 8-item set (polish on a surface with no evidence of use); dropping
the site work entirely (loses the two hand-off fixes, which are real regardless).
**Affects:** `pb/tools/render.py` (`_default_props`), `pb/tools/lint_registry.py`,
`pb/template/design-system.html`, the spec sidecar shape
**Reviewed via:** the real DS site at `:8200/design-system`, measured in-page; plus a search of the real
project for any reference to the site (none)

## D-25 · The prototype gains a link to the design-system site, outside the tab strip — 2026-09-19
**Problem:** #3 — one registry → two sites, but only one is reachable
**Decision:** Add a `/` → `/design-system` link to the shell's header. It must **not** carry
`.meta-tab` (that class is counted by `tests/e2e_smoke.py:124,191`, which assert exactly 4), and it is
**protocol-gated** — rendered only when `location.protocol` is http/https, so a `file://` hand-off
never shows a link that 404s.
**Why:** v1.11 shipped two sites and one preview server serving both, and the prototype has no way to
reach the second. Measured on the real project: zero anchors matching `design-system` in the rendered
page.
**Alternatives rejected:** a fifth `.meta-tab` (breaks two tests, and it is a different site not a tab);
always rendering it (404s in every `--people` hand-off, which is the most-shared artifact pb produces).
**Affects:** `pb/template/prototype.html`, `tests/e2e_smoke.py` (unchanged — that is the point)
**Reviewed via:** `document.querySelector('a[href*="design-system"]')` → null on the real project

## D-24 · The Data tab gets findability from parts already paid for — 2026-09-19
**Problem:** #3 — the Data tab at real scale
**Decision:** Four changes, no new tools:
1. **Search** — render the input **once** into `.erd-toolbar`'s empty right slot and repaint only the
   table host. **Not** focus restoration.
2. **Sort** — wire the shell's existing `pbSortTable(th)` (already at :2513, numeric-aware) to the
   entity tables' `<th>`s. Zero new JS.
3. **Notes** — clamp the cell to a few lines with an expand control.
4. **`origin`** — surface it as a **row tint + legend**, not a fifth column (width is already tight),
   upstreaming what the real project forked its shell to get (`.erd-row-keep` / `.erd-entity-keep`).
Plus: the **variant switcher stays**, and its emptiness is reported as an *authoring* gap by
`lint --report` ([D-22]), not treated as a code defect.
**Why:** measured on the real project's Data tab — **15,911 px** of continuous scroll, **16 tables /
200 rows**, and **no way to find anything**: 0 sortable headers, no search, no filter. Three of the four
fixes use parts that already exist and are unused — `pbSortTable` is shipped but wired to nothing, the
toolbar's right slot is empty in Table view (a zero-CSS home), and `origin` is populated on **198 of
200 rows** while the shell ignores it. The notes column is the height driver: **50 rows exceed 120
characters, the longest is 1,444**. The variant switcher — v1.5's headline Data feature — renders
**0 switchers** here, because the project authored no `erd.mock` sets in two months.
**The focus constraint is confirmed, not assumed:** every view setter does `$('#app').innerHTML = …`,
so an input inside it loses focus per keystroke. With a Vietnamese keyboard that breaks IME composition
mid-word, not merely the caret — which is why restoration is rejected outright.
**Alternatives rejected:** focus restoration (breaks IME); `.pb-content--full` (caps at 960 px — and the
tab already uses plain `.pb-content`, so the plan's worry did not apply); a fifth column for `origin`.
**Affects:** `pb/template/prototype.html` (`renderMetaERD`, `pbErdMain`, `.erd-toolbar` CSS)
**Reviewed via:** the real project at `:8200`, Data → Table, measured in-page

## D-23 · A tool is only justified when a prompt cannot do the job — 2026-09-19
**Problem:** process — scope discipline for Phase B
**Decision:** Standing test before any new `pb/tools/*.py` is proposed. A tool is justified **only** if
at least one holds: **(a)** it runs inside the deterministic render path at ~0 model tokens
(CLAUDE.md rule #2, so a prompt physically cannot do it); **(b)** it needs a regression test —
especially a false-positive corpus — which a prompt cannot have; **(c)** it is arithmetic over a large
set where a model is slow and non-deterministic. Otherwise the job belongs in a command prompt (which
already has grep, read-with-offset and the whole tool surface), or as a flag on an existing tool.
**Why:** the user challenged the growing tool count and was right on half of it. Applying the test
retroactively cut the W3/W4 proposals from four new tools to two and from one new command to none. The
test also reframes W8: a contract is a **process** fix, and the checker should be sized only to the gap
the process leaves — not designed first and justified after.
**Alternatives rejected:** case-by-case judgement (that is what produced the four); a hard cap on tool
count (arbitrary — the ripple extractor is genuinely unavoidable).
**Affects:** Phase B scope; W8's ordering (contract and writing discipline first, checker sized after)
**Reviewed via:** applied to all four W3/W4 proposals, results in [D-21] and [D-22]

## D-22 · Health reporting is a `--report` flag on lint, not a new `doctor.py` — 2026-09-19
**Problem:** #3 project health — placement (amends [D-18])
**Decision:** `lint_registry.py --report` prints the histogram by code, the top items by finding count,
the measured size/shape metrics and the ranked "what to fix first", and **always exits 0**. No new file.
Everything [D-18] decided about behaviour — ranks never gates, mandatory FP guards, the
information-vs-finding rule, thresholds in an optional `memory/doctor.json` — is unchanged.
**Why:** [D-23]'s test. `lint_registry.py` already exposes `check(reg, strict, base_dir)` returning a
findings list and `_report()` for output; the histogram is arithmetic over that list. A separate file
would import lint, re-implement its CLI, and add a second thing to keep in step for no gain.
**Alternatives rejected:** a standalone `doctor.py` ([D-18] as first written — a new file for a flag's
worth of work); a command (nothing to type that `/pb:check-drift` cannot host).
**Affects:** `pb/tools/lint_registry.py`, `pb/commands/check-drift.md`, `tests/` (FP corpus)
**Reviewed via:** lint's `check()`/`_report()` seam read directly; the flag fits without restructuring

## D-21 · Fix the writers of the decisions log, not its readers — 2026-09-19
**Problem:** #3 the why-log (supersedes the plan's `why_index.py` + `/pb:decisions`)
**Decision:** **No index tool and no new command.** Instead:
1. `pb/commands/build.md` §3 gate — **before** appending a drift override, grep `memory/decisions*.md`
   for the slice being touched and show any prior decision on it, then ask.
2. `pb/commands/clarify.md` — same read before appending a trade-off.
3. Both write a **consistent entry shape** (`## <date> — <title>` + `- **Decision:**` / `- **Why:**` /
   `- **Affects:**`), so grep stays reliable as the file grows.
4. **Rotation stays code** — it moves data and must assert the move was lossless — but ships as a mode
   on an existing tool, not a new one. Trigger on **size (500 KB default), never on the calendar.**
5. Widen the hand-off bundle glob to `memory/decisions*.md` **in the same commit** as rotation.
**Why:** the defect is not that an 818 KB file is hard to search — it is that **three commands write
that file and none reads it**. `init.md` creates it, `build.md` appends on a gate override,
`clarify.md` appends per trade-off; `build.md` §3 reads `constitution.md` → Principles and never opens
`decisions.md` before appending to it. That is why the real log has entries marked SUPERSEDED the same
day they were written. A reader tool would have made a broken process searchable instead of fixing it.
Rotation by year is also dead on arrival: the real log is **187 entries / 818 KB in two months**
(2026-07: 86, 2026-08: 100) — a year rule would never fire on the project that needs it.
**Also corrected:** `/pb:why` **does not exist** anywhere in the repo — the plan's "rename to
`/pb:decisions`" was wrong, so no compat alias is owed. And my W3 claim that the real log ignores the
house format was a bad grep: it uses it as **list items** (411 `- **Field:**` markers — Affects 164,
Decision 76, Why 40, Alternatives 29), and **95% of entries carry at least one recognised field**.
Field names vary (`Verified` / `Verification`), which is what the writers' shape fix closes.
**Alternatives rejected:** `why_index.py` + `/pb:decisions` (the plan — a reader for a write-only
process); folding search into `/pb:check-drift` (better, but still treats the symptom).
**Affects:** `pb/commands/{build,clarify,handoff-close}.md`, `pb/template/decisions.template.md`,
rotation mode on an existing tool
**Reviewed via:** a throwaway tolerant parser on the real log (187 entries, index 20 KB vs 875 KB,
209k tokens → 4k) — which is what proved the *reader* was the wrong half of the problem

## D-20 · The render budget covers the whole pipeline, at real scale — 2026-09-19
**Problem:** #3 project health — an unmeasured slow step
**Decision:** Extend `tests/render_budget.py` beyond `build_html` on a 50-component synthetic:
budget **`load_specs` + `build_html`** together, and run the case at real scale via
`tests/scale_fixture.py` (the Phase B promotion of the synthetic generator). Keep
`BUDGET_MS = 100` for `build_html` and add a separate, larger budget for the pipeline so a
regression in sidecar loading cannot hide.
**Why:** measured on the real project — `json.load` 2.6 ms, **`load_specs` 17.1 ms**, `build_html`
9.9 ms. The slowest step is the one no test watches, and the budget that does exist runs on a
fixture a third the size of a real project. W2's ripple extraction will add a third step to the same
pipeline, so the envelope has to be real before that lands.
**Alternatives rejected:** raising `BUDGET_MS` (hides the gap); timing in CI only (no local signal).
**Affects:** `tests/render_budget.py`, `tests/scale_fixture.py`
**Reviewed via:** timings above, taken through the repo's own `render.py` on the real registry

## D-19 · `staleness` is deprecated, not deleted — 2026-09-19
**Problem:** #3 project health — a dead slice
**Decision:** Stop seeding `staleness` in `registry.template.json`, mark it deprecated in the schema
notes, and leave the shell's `pbStalenessGap` reader tolerant of its absence (it already returns 0).
**Removal waits for a later major release**, per `AGENTS.md` ("never remove or repurpose an existing
field in place — add, then deprecate later"). Doctor reports a present-but-all-zero `staleness` as
information, never a finding.
**Why:** the slice is seeded by the template and read by the shell, and **nothing in the entire
plugin has ever written it** — no tool, no command. The gap it computes is permanently zero, so the
staleness UI it feeds is dead chrome. The user accepted removal; governance turns that into a
deprecation.
**Alternatives rejected:** deleting it now (breaks the governance rule and any project that reads it);
wiring a real prompt counter (no component of pb counts prompts, and inventing one to feed dead chrome
is the wrong direction).
**Affects:** `pb/template/registry.template.json`, `docs/architecture.md`, `pb/tools/doctor.py`
**Reviewed via:** repo-wide search for a writer — zero hits outside the template and the shell reader

## D-18 · Health reporting ranks and never gates; every check carries a false-positive guard — 2026-09-19
**Amended by [D-22] the same day:** the *placement* changed (a `--report` flag on `lint_registry.py`, not a new `doctor.py`). Everything else below stands.
**Problem:** #3, #6, #7 project health
**Decision:** A new `pb/tools/doctor.py` that **imports** `lint_registry.check()` and reports:
a histogram by code, the top items by finding count, the measured size/shape metrics, and a ranked
"what to fix first". It **always exits 0** — it reports and ranks, never fails a build. Thresholds live
in an optional `memory/doctor.json` (absent → built-in defaults), which is what keeps this at schema 10
with no bump. Every check carries an explicit FP guard, and **any check that cannot get its false
positives below roughly one in ten ships as INFORMATION, not as a finding** — unused tokens ship as
information. Extends the Kind A / Kind B taxonomy of [D-08] from `logic_check.py` to doctor.
**Why:** measured on the real project, twice over. Lint emits **96 warnings / 0 errors** as a flat list
— unreadable; the histogram is 4 codes and one component carries 8 of them, so *ranking* is the
product. And the naive checks were wrong: **orphan components 36 → 0** (every one was reached by a
direct `renderCmp*` call, the sidebar case, or is the deliberate fake-module pattern) and **unused
tokens 182 → 120** once runtime-composed names are honoured — and an unused design-system token is not
a defect at all, since a DS ships full ramps. A health tool that cries wolf is worse than none.
**Default thresholds, measured:** body >500 lines (14 on the real project) · >1000 lines (6, max 4,213)
· registry >500 KB (927 KB) · a single slice >20 KB · decisions log >500 KB (818 KB).
**Alternatives rejected:** new `R-*` codes inside lint (drowns in the existing 96); a failing exit code
(a health report that blocks a build gets disabled); thresholds in `registry.json` (forces a bump).
**Affects:** `pb/tools/doctor.py`, `pb/commands/check-drift.md`, `tests/doctor.py` (FP corpus)
**Reviewed via:** the naive-vs-guarded counts above, run on the real project

## D-17 · The slice tool gains field projection, not `--body` — 2026-09-19
**Problem:** #3 — the token lever fails at real scale
**Decision:** `slice.py get` gains field projection — `--no-prose` (drop `logicNotes`, `uiLogic`,
`anatomy`, `spec`, `usage`) and `--fields a,b,c`. **This supersedes the plan's `slice.py --body`**,
which solved a different problem than the one the measurement found.
**Why:** measured on the real project — reading one screen slice costs **76,432 B**, and **71% of it is
`logicNotes` prose**. Across the registry `logicNotes` is **370 KB (39%)** and `elements[]` another
**94 KB (10%)**: half the file is prose the build loop never edits. Projecting prose out takes all
screens from 393 KB → 108 KB and the biggest component slice from 27,700 B → **1,631 B (95% smaller)**.
The body files were never the problem the flag assumed — they are already out of the registry behind
`renderSrc`, and a body is read deliberately.
**Alternatives rejected:** `--body` (reads a file the caller can already open by its `renderSrc`);
splitting the 4,213-line shared body (it is correctly shared by three screens); moving `logicNotes` to
a sidecar now (that is W8's contract, and it must not be pre-empted by a convenience flag).
**Affects:** `pb/tools/slice.py`, `tests/slice_cli.py`, `pb/commands/build.md`
**Reviewed via:** byte counts above, taken with the repo's own `slice.py` against the real registry

## D-16 · The `ia` slice: three-field jobs + declared layer purposes; everything else derived — 2026-09-19
**Problem:** #1 (IA sub-tab) — what is stored vs what is computed
**Decision:** The registry gains an additive `ia` slice with exactly two authored things:
`jobs[]` (`id`, `roles[]`, `when`, `want`, `so`, `priority`, `screens[]`, optional `source`,
optional `story`) and `layers[]` (`depth`, `name`, `purpose`). **Everything else the tab shows is
derived at render time** — layer membership, parent/child edges, overlays, per-layer role sets, the
"Solves" line, coverage counts, and the unassigned/uncovered warnings. `/pb:init` gains a JTBD intake
(Q&A or extracted from the PRD) that seeds `jobs[]` and asks one sentence per layer; `/pb:plan` maps
jobs → screens; `/pb:build` warns when it creates a screen no job points at. `flow.stories[]` keeps
its prose `jtbd` and gains `jobs[]` (ids) so a flow path and a job reference each other. A screen with
no job is drawn as a **warning, never a blocker**. Default sub-tab: Information Architecture when
`ia.jobs` is non-empty, User Flow otherwise.
**Why:** the W2b build proved the graph is free — the sidebar literal plus the nav calls already
encode the hierarchy, so asking an author to re-draw it would invite drift. Only intent must be
authored: the job's situation/motivation/outcome, and what each layer is *for*. Splitting the job into
three fields (rather than one sentence) is what makes the derived "Solves" line possible.
**Alternatives rejected:** storing the site map (drifts from the bodies immediately); one free-text
`job` string (cannot derive outcomes, and the user's first review rejected exactly that); reusing
`flow.stories[]` alone (a story is a narrative through one flow, a job is a standing need).
**Affects:** `pb/migrations/0009_*.py` (with the logic contract), `pb/commands/{init,plan,build}.md`,
`pb/template/prototype.html`, `pb/agents/pb-clarifier.md`, `pb-planner.md`
**Reviewed via:** the same `:8300` build as [D-15] — 16 jobs, 10 screens, 2 unassigned jobs, 0
uncovered screens on the real project
**Caveat recorded:** the derived "Solves" line is only as good as the `so` clauses; vague outcomes
produce a vague layer. The intake prompt must show a worked example.

## D-15 · Information Architecture: jobs-to-be-done as the coverage map, intake at `/pb:init` — 2026-09-19
**Problem:** #1 logic visibility (extended by the user during the W2 review)
**Decision:** A third UX Design sub-tab, **Information Architecture**: every user job (JTBD) as a tag,
filterable by role; jobs grouped under the screen(s) that serve them so coverage is visible; jobs that
map to **no** screen listed apart with a call to action; `/pb:init` gains a JTBD intake step (Q&A or
from the PRD) that seeds the jobs. Shape and schema to be settled in the W2b quick build.
**Why:** the user's framing — the prototype should prove it covers every job the roles have, and a new
job should surface as unassigned work rather than disappear into prose.
**Alternatives rejected:** reusing `flow.stories[]` as-is (stories are per-flow narratives, not the
role's job list); a Project Summary section (it is structure, not summary).
**Affects:** `pb/template/prototype.html` (UX Design), `pb/commands/init.md`, schema (a new `ia`
slice — additive; earns its bump alongside the logic contract), `pb-clarifier`/`pb-planner` agents
**Reviewed via:** W2b quick build on the real project at `:8300`, two rounds.
**Outcome — data model accepted, presentation NOT accepted.** Round 1 drew jobs as flat tags per
screen; the user rejected two things: no page-to-page relation (*"how many layer, each layer is
solving what problem?"*) and jobs not written to the JTBD standard. Round 2 fixed both in the data:
**layer membership and edges are DERIVED** (layer 0 = every screen a sidebar item targets; deeper
layers from `data-nav` / `data-go` / `setProtoScreen` in the bodies, plus `activeScreenId` as the
fallback parent; overlays = the drawer/modal/dialog components each screen composes) and **jobs are
stored as three fields** (`when` / `want` / `so`), rendered "Khi …, tôi muốn …, để …". On the real
project this derives **2 page layers + 1 overlay layer**: L0 = 6 sidebar screens / all 5 roles,
L1 = 4 detail screens / HR only (4 nav edges, all out of two L0 screens), overlay = 7 components.
A layer's **"Solves"** line is composed from the `so` clauses of the jobs on it. The user's verdict on
round 2: *"not really good but continue to W3, we will improve UI later"* — so the **data contract is
settled and the visual design is explicitly deferred** to an implementation-time UI pass (Phase B),
not re-opened in Phase A.

## D-14 · The Logic view lives in UX Design, which becomes three sub-tabs — 2026-09-19
**Problem:** #1 logic visibility — placement (revises D-03)
**Decision:** The Logic view (Rules | Ripple) moves from Project Summary to the **UX Design** tab, which
gains `meta-subtab` navigation: **Information Architecture · User Flow · Logic**. The existing flow
canvas + stories/test-cases split becomes the User Flow sub-tab unchanged. Project Summary keeps its
four sub-tabs; "UI Logic Trade-offs" is left as is (no longer a naming clash).
**Why:** the user judged the view structural (how the product is wired) rather than summary; UX Design
is where flows and stories already live, so rule → flow → screen reads left to right in one tab. Still
no fifth top-level tab, so `tests/e2e_smoke.py:124,191` stay green.
**Alternatives rejected:** Project Summary sub-tab (D-03, superseded); a fifth tab (breaks two tests).
**Affects:** `pb/template/prototype.html` (`renderMetaFlow`, `TAB_INFO.flow`), `CLAUDE.md` tab table,
`docs/architecture.md`
**Reviewed via:** W2 quick build at `:8300` (Project Summary placement); re-built under UX Design in W2b

## D-13 · Logic view = declared Rules first, derived Ripple second; dead reads visible; SVG state machines — 2026-09-19
**Problem:** #1 logic visibility — the lens (closes D-04)
**Decision:** One view, two lenses. **Rules** (declared: state machines, matrices) render with five
derived footers — implemented by, read by, displayed in, decided in, source. **Ripple** (derived at
render time by a `load_logic()` step, always on when render bodies exist) shows, for a handler / store
slice / component, what it reads, which slices it touches (with the helper path, two hops), what it
re-renders. Every fact is badged **derived** or **declared**. Dead reads stay visible as struck-through
chips. State machines are hand-drawn SVG (overlay bands have no Mermaid equivalent).
**Why:** the user's own artefacts (cycle-status table, permission matrix) are rules, and the code
implements each as one function — the link is real and cheap to derive. Two-hop tracing turned
`kpiSets` from 1 reader into 51: that is the blast radius a designer needs. Static derivation can trace
**reads but not writes** (mutations happen inside store helpers), so writers must be *declared* — the
strongest argument for the W8 contract carrying `writes[]`.
**Alternatives rejected:** impact-only lens (loses the rule → code link); interaction-trace (needs a
browser); Mermaid stateDiagram (no overlays).
**Affects:** `pb/tools/render.py` (`load_logic`), `pb/tools/logic_extract.py`, the shell, W8 contract
(`writes[]`, `implementedBy[]`, `displayedIn` derived), `tests/render_budget.py` (extraction must fit
the 100 ms budget — unmeasured; graph is 293 KB inlined on the real project, page 4.5 → 4.8 MB)
**Reviewed via:** scratch shell on the real project at `:8300`, console clean on both lenses

## D-12 · The logic checker is its own tool, sharing lint's Finding contract — 2026-09-19
**Problem:** W1 logic census (#4 composition drift, #1)
**Decision:** `pb/tools/logic_check.py` (+ `logic_extract.py` as its parser), copying `lint_registry.py`'s
`Finding`/`_report`/exit-code contract, run on request and by doctor — **not** an extension of lint.
**Why:** lint runs on every write path and already emits 96 warnings on the real project; logic findings
buried under that stop being read. Separate exit codes let doctor rank them.
**Alternatives rejected:** new `R-LOGIC-*` codes inside lint (drowns), a browser-driven check (W7 owns that).
**Affects:** `pb/tools/logic_check.py`, `pb/tools/logic_extract.py`, `tests/logic_check.py` (FP corpus)
**Reviewed via:** scratchpad `logic_extract.py` on the real project, output saved as `w1-census.txt`

## D-11 · `--sync-elements` is append-only and never on a write path — 2026-09-19
**Problem:** W1 — 65 `R-COMPOSE-MATCH` warnings
**Decision:** `lint_registry.py --sync-elements` appends a `screens[].elements[]` entry for every composed
`orgId` not yet declared (label `"(auto) composed <id>"`, `state:"default"`), **never edits or removes**
an existing entry, and prints declared-but-not-composed as findings instead of deleting them. Runs only
when asked; never from `/pb:build`.
**Why:** the real project's 208 `elements[]` entries carry hand-written labels (avg 345 chars, 111 with a
date) and `tokens[]`; a rewrite would destroy them. Measured: 66 composed-not-declared, **0**
declared-not-composed — so append-only clears the screen half completely.
**Alternatives rejected:** regenerate `elements[]` from the body (data loss); auto-run on render (surprise writes).
**Affects:** `pb/tools/lint_registry.py`, `pb/commands/build.md`
**Reviewed via:** per-screen diff of `pbUse` ids vs `elements[].orgId` on the real registry

## D-10 · R-NEST accepts local children; R-NEST-HINT matches whole tokens — 2026-09-19
**Problem:** W1 — the R-NEST / R-COMPOSE-MATCH contradiction
**Decision:** `anatomy.parts[].orgId` may reference **any** registry component. `R-NEST` stays an ERROR
only for an id that resolves to nothing; the Figma-key concern stays with `R-NEST-FIGMA`. `R-NEST-HINT`
changes from substring (`g in name.lower()`) to whole-token equality on the part name. Both ship in one
increment with `--sync-elements` (D-11).
**Why:** non-atom components compose 132 local-child edges; of the 57 components carrying the
composed-not-declared warning, only 4 can be cleared by declaring globals, 39 are blocked entirely and 14
mixed — the two rules contradict each other by construction. `registry_to_figma.py` already lowers a
non-DS child as a FRAME from anatomy, so the restriction guards nothing. All 12 `R-NEST-HINT` hits are
substring accidents ("optional tabs" → `tabs`, "Toggle Input" → `input`).
**Alternatives rejected:** add a separate `localId` field (two fields for one edge); drop `R-NEST-HINT`
(keeps a useful drift detector at zero cost once precise).
**Affects:** `pb/tools/lint_registry.py`, `docs/architecture.md`, `changelog.md`
**Reviewed via:** decomposition of the 57 carriers on the real registry (4 / 39 / 14)

## D-09 · Which of the project's gates upstream, and in what form — 2026-09-19
**Problem:** W1 — 1,019 lines of hand-rolled gates in the real project
**Decision:** G2 seam → the **baseline-free cross-check** (consumed-but-never-produced), Kind A. G3
`:has()` → R1/R2 as checks, R3 as a note, R4 (rule count) **never**. G1 byte-freeze → opt-in
`logic_check.py --freeze --capture|--check`, never a standing gate. G4 role affordances → **W7**
(`present`/`absent` expects in `test_run.py`), not this tool. `token_sweep` → W3 doctor.
**Why:** the cross-check needs no baseline and found **10** dead reads the project's own G2 could not
see (its baseline was re-captured after the 2026-08-10 deletion that orphaned them); all 10 are `if (el)`
guarded → WARN. `:has()` is healthy on the real project (80 static rule sites, 222 occurrences, 0 R1/R2,
1 R3 note) — keep the mechanism, enforce the invariants. The freeze is the only proof of "UI-only change"
but is meaningless without a wave boundary, so it stays opt-in.
**Alternatives rejected:** shipping the baseline diff (inherits the staleness FP class); gating on counts.
**Affects:** `pb/tools/logic_check.py`, `pb/tools/test_run.py` (W7), `pb/tools/doctor.py` (W3)
**Reviewed via:** the project's gates run read-only beside the scratch extractor; 4 extractor FP classes
fixed first (prop-passed ids, variable prefixes, runtime `setAttribute`, `name`/`idPrefix` props) —
residual 10/10 confirmed genuine by hand

## D-08 · Two kinds of logic check; absence of a declaration is never a finding — 2026-09-19
**Problem:** W1 — false-positive discipline (the project's gates were wrong every time but one)
**Decision:** Every check is **Kind A** (derived vs derived — a contradiction inside the code: dead seam,
undefined or duplicate helper, R1/R2 violation; ERROR, or WARN when runtime-guarded) or **Kind B**
(declared vs observed — `elements[]` vs `pbUse`, `anatomy.parts[]` vs `pbUse`, a rule's `implementedBy`
vs the body; prints both sides and the author's `why`; **absence of a declaration is never a finding**).
No check gates on a count, ratio or baseline hash by default. Every field FP becomes a fixture before
the fix; `--explain <CODE>` prints a rule's rationale and known FP modes.
**Why:** the census itself demonstrated it — the first extractor pass reported 24 missing ids, 23 were
producer forms it did not read. A tool that cries wolf gets ignored, then masks the real hit.
**Alternatives rejected:** a single severity ladder; heuristics that infer intent from names.
**Affects:** `pb/tools/logic_check.py`, `tests/logic_check.py`, `docs/architecture.md`
**Reviewed via:** W1 census on the real project — 575 top-level fns (143 render / 432 logic in 30 of 141
bodies), 148 cross-file helpers, 0 undefined, 0 duplicate; the 4-FP-class → 10 true-positive trajectory

## D-07 · Land the P0 render fix now, as v1.11.1, ahead of Phase B — 2026-09-19
**Problem:** the P0 from D-06 (pb v1.11.0 cannot render a real project)
**Decision:** Break the "no production code in Phase A" rule **once, deliberately**: ship the narrow
`</script`-only escape immediately on `release/v1.11.1` as its own tiny PR (commit `bfbc9b2`), with
`tests/render_escape.py` as the regression guard. Scope held to the fix, the test, the changelog, one
doc line and the version bump — `.gitignore` (`/.reference/`) and this log stay out of it and land with I1.
**Why:** a builder that renders a real project blank on both routes is not something to leave open for
the weeks Phase A takes; the fix is one regex at one call site, both render targets share it, and the
test proves the emitted script parses (with a negative control on the old behaviour). User's call.
**Alternatives rejected:** waiting for I1 (leaves every real user on a hand-patched plugin cache);
folding the Phase A housekeeping into the same PR (muddies a P0 review).
**Affects:** `pb/tools/render.py`, `tests/render_escape.py`, `changelog.md`, `docs/architecture.md`,
`plugin.json` ×2, `marketplace.json`, `README.md`, `CLAUDE.md` — version 1.11.0 → 1.11.1
**Reviewed via:** full sweep 18 passed · 3 Playwright skips · 0 failed; the real project renders through
the repo's own `render.py` and `serve.py` with 0 mangled literals on both targets. PR: human merges.

## D-06 · The review workbench runs on a scratchpad narrow-escape copy of `pb/tools`; the fix is proposed as I1's P0 — 2026-09-19
**Problem:** W0 → a new **P0**: pb v1.11.0 cannot render Atlas at all.
**Decision:** Serve the real project through a *scratchpad* copy of `pb/tools/` whose `_escape_body`
escapes **only `</script`** (Atlas G0's "narrow escape"), passing pb's shipped shells explicitly, so
the review could proceed with the repo untouched. **Superseded the same day by D-07:** the fix was
landed in the repo as v1.11.1 (`bfbc9b2`); the scratch copy is deleted and `:8200` now runs on the
repo's own `serve.py`.
**Why:** `render.py:_escape_body` does a blanket `"</" → "<\/"` (since `906223e`, kept at `20576a0`).
That turns the JS regex literal `/</g` — a standard HTML-escape idiom present in **17 Atlas render
bodies** — into `/<\/g`, an unterminated regex that kills the entire inline script: **both routes render
blank** (`Uncaught SyntaxError: Invalid regular expression: /<\/g, '&lt;').replace(/`). Atlas's
`gates/preflight.py` G0 documents this verbatim and probes for the narrow behaviour; Atlas's
`launch.json` points at a plugin cache on another machine (`/Users/<user>/…`) that must carry a
hand-patched `render.py`. **pb upstream never received the fix**, so Atlas's working setup is a
works-on-my-machine dependency. Only `</script` terminates a script element (HTML spec), so escaping
it alone is sufficient and correct.
**Alternatives rejected:** fixing `render.py` in the repo now (Phase A forbids production code);
serving Atlas's forked shell (the bug is in render.py, not the shell); rewriting the 17 bodies (they
are correct JS — the tool is wrong).
**Affects:** `pb/tools/render.py` (I1, P0); a new regression test; the synthetic fixture (add a body
using `/</g` so it reproduces the hazard — today it dodges it by luck).
**Reviewed via:** G0 probe PASS on the scratch copy; `:8200` serves both routes, 0 mangled `/<\/g`,
19 healthy (17 bodies + 2 shell).
**Related finding — Atlas's forked shell** (`prototype/template/prototype.html`, 6,275 vs 6,223
lines, 9 hunks; diff saved to scratch). Mostly features pb lacks, routed to their sessions:
ERD `origin` flag CSS+JS (`.erd-entity-keep`/`.erd-row-keep`, brand-blue "kept" rows) → **W5**;
"chromeless prototype stage" (hides `.proto-tabbar/.proto-navbar/.proto-appbar`, flattens the
laptop frame — user instruction *"bỏ hết, phẳng hoàn toàn"*) → **W5/W6** device-chrome decision;
SheetJS CDN `<script>` injected for `bulk-excel-engine.js` because pb cannot declare a runtime
dependency → **W8** (`registry.runtime[]`); scenario-title scoping → **W7**; a flow-connector tweak → W2.

## D-05 · Real Atlas cloned in-repo as a temporary reference; the synthetic fixture stays the permanent one — 2026-09-19
**Problem:** W0 review workbench
**Decision:** Clone the reference project's private repository into `.reference/atlas/` — gitignored,
never committed — so Phase A reviews run against the **real** registry through the existing
`serve.py`. The synthetic `scale_fixture.py` is still promoted in Phase B as the permanent,
committable at-scale test fixture. **The clone is erased when the remediation ends** (obligation
recorded in durable memory as well).
**Why:** No synthetic stand-in matches real screens for review fidelity — the user judged the
synthetic one unrecognisable as the product even after switching to the performance-management
vocabulary. But internal product data cannot ship in a repo that *is* the plugin's distribution
artifact, so the permanent fixture must remain synthetic and leak-free.
**Alternatives rejected:** Synthetic-only review (insufficient fidelity); committing the real project
as a fixture (leaks internal data into every release).
**Affects:** `.gitignore` (`/.reference/`), the W0–W8 review workflow, Phase B fixture promotion
**Reviewed via:** three routes screenshotted on the synthetic fixture at `:8100`; the real clone
is the next review surface
**Note (after cloning):** the pb project is not on `master` — it lives on branch
`its active feature branch`, which is what `.reference/atlas` checks out. GitHub is one commit
behind the local working copy (the pushed head vs the local one, plus 5 uncommitted local files), so the
reference is the *pushed* state. The clone's committed `node_modules`/`dist` (415 MB) were pruned
from the throwaway copy; it is 73 MB. Served read-only at `:8200`; the synthetic fixture stays at `:8100`.

## D-04 · Ripple lens deferred to its own session — 2026-09-19
**Problem:** #1 Logic visibility
**Decision:** The primary question the ripple view answers (impact · interaction-trace · store-centric)
is decided in the W2 deep-dive, not up front.
**Why:** The W1 census extractor produces the raw material for all three lenses; choosing before
seeing that data would be guessing. The user asked to focus on the big plan first.
**Alternatives rejected:** Committing to "impact" now (my recommendation) — premature without census output.
**Affects:** W2 scope; `pb/template/prototype.html` (Project Summary renderer)
**Reviewed via:** n/a

## D-03 · Ripple view is a Project Summary sub-tab, not a 5th tab — 2026-09-19
**Problem:** #1 Logic visibility
**Decision:** Logic/ripple visibility lives as a sub-tab of Project Summary (tab 2), alongside
Overview · Insights · Trade-offs · Others.
**Why:** The user framed logic as "UI logic that may affect each other" — summary-level context, not a
separate workspace. It also sidesteps `tests/e2e_smoke.py:124,191`, which assert the `.meta-tab`
count is exactly 4.
**Alternatives rejected:** A 5th top-level tab (breaks two tests; and a tab with no content is worse
than no tab).
**Affects:** `pb/template/prototype.html` (`meta-subtab`, `TAB_INFO`), W2
**Reviewed via:** n/a

## D-02 · One PR per increment — 2026-09-19
**Problem:** process
**Decision:** Each increment ships on its own `release/vX.Y.Z` branch as one PR; the human merges.
**Why:** Matches `AGENTS.md` §4 literally, keeps every revert cheap, and each PR is reviewable in one
sitting. Phase B's workflow produces the branches; the user merges them.
**Alternatives rejected:** Two grouped releases (scale, then logic) — PRs too large to review well.
**Affects:** Phase B orchestration; `changelog.md`, `plugin.json` per release
**Reviewed via:** n/a

## D-01 · Schema bumps accepted when earned — 2026-09-19
**Problem:** process / #1
**Decision:** The scale work (workbench, doctor, decisions index, Data tab, DS site) stays at schema
10 with no bump. The logic contract takes schema 11 via migration `0009`, proven on a copy of Atlas
and rolled back to byte-equality before shipping.
**Why:** `AGENTS.md` §3 permits additive bumps with a numbered, reversible migration. Forcing the
contract into convention-discovered sidecars (no `logicSrc`) would leave nothing to validate the link.
**Alternatives rejected:** Stay at 10 everywhere (weaker — lint can't flag an orphaned contract); one
batched bump later (blocks the ripple view until the whole batch is ready).
**Affects:** `pb/migrations/manifest.py`, `pb/migrations/0009_*.py`, W8
**Reviewed via:** n/a
