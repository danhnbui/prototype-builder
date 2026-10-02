# Changelog

All notable changes to Product Builder. Format follows [Keep a Changelog](https://keepachangelog.com/).

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
