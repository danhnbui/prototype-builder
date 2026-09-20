# Product Builder — playbook

The detailed reference behind the [router](CLAUDE.md). Read the router first. This file
documents the `registry.json` data contract, the render-function inventory, the sync rules,
and component governance. (Sections marked _(Phase N)_ are filled as those phases land.)

## registry.json — the data contract

`registry.json` is the **single source of truth** the build loop edits. `prototype.html` is a
rendered **view** — a derived hand-off snapshot, not a parallel preview (the one live preview is the
`/pb:preview` server over `registry.json`): at `/pb:build --render` the generator inlines `registry.json` into the HTML's
`PB_REGISTRY`, and a thin adapter (`adaptRegistryToPBData`) maps it onto the in-memory `PB_DATA`
shape the render machinery already reads — so the ported v0.4.0 render functions are unchanged.
**Data only:** the registry holds **no render code**. As of v1.4 (schema 4) each component/screen
carries a `renderSrc` pointing at a real `.js` body file (`render/components/<id>.js`,
`render/screens/<id>.js`, resolved relative to the registry); `render.py` reads those files and
generates the render functions at `/pb:build --render`. Edit the `.js` files directly — they are
lintable and diffable. (A legacy inline `render` string still renders for backward compatibility;
`renderSrc` wins when both are present, and `lint_registry.py` warns to remove the inline copy.) Design
tokens are applied onto `:root` at boot via `applyRegistryTokens`.

### Top-level shape

| Key | Type | Feeds | Notes |
|---|---|---|---|
| `meta.name` | string | — | project name |
| `meta.shell` | `'browser'\|'app'` | Prototype | default preview chrome — `browser` (tab strip + back/reload/URL bar) or `app` (plain titlebar on desktop; a contrast-aware device status bar on tablet/mobile). Viewer can toggle live; set at `/pb:init`. Defaults to `'browser'` |
| `meta.device` | `'monitor'\|'laptop'\|'tablet'\|'mobile'` | Prototype | default device for the preview frame; set at `/pb:init`. Falls back to `'laptop'`. Legacy `'desktop'` → `'laptop'` |
| `meta.devices` | `('monitor'\|'laptop'\|'tablet'\|'mobile')[]` | Prototype | the fixed sizes this project supports (`monitor 1920×1080 · laptop 1280×832 · tablet 834×1112 · mobile 390×844`) — unsupported sizes are disabled in the switcher. Optional; defaults to all four. Legacy `'desktop'` expands to `monitor`+`laptop` |
| `meta.designSystem` | `{ name, designLink, codeLibrary, linked }` | design-system site | the linked design system — `designLink` (Figma/doc URL), `codeLibrary` (folder path or repo URL). Seeded from the DS Lock at `/pb:init`. Optional/tolerated-absent → the DS bar shows an "add one" affordance |
| `meta.platform` | `'web'\|'ios'\|'android'\|'desktop'` | — | the DS/target platform; set at `/pb:init`. Defaults to `'web'`. Schema 5 (v1.6) |
| `meta.dsSource` | `{ type, ref, clonedAt } \| null` | — | provenance of the cloned DS: `type ∈ figma\|code-library\|mcp\|common`, `ref` the literal URL/path/name, `clonedAt` ISO stamp. `null` until `/pb:pull-ds` clones. The full token/component snapshot lives in `design-system/<name>/.source.json`; `/pb:test --drift` §5 diffs the live source against it. Schema 5 (v1.6) |
| `meta.outputTier` | `'host'\|'scaffold'\|'hardened'` | — | which export tier `/pb:handoff` targets. `host` = the runnable single-file prototype; `scaffold` = deterministic React+Tailwind (`render_react.py`); `hardened` = idiomatic/DS-integrated (deferred). Defaults to `host`. Schema 6 (v1.7) |
| `meta.exportTarget` | string \| null | — | machine-readable export target mirroring the Stack Lock (e.g. `'react-tailwind'`); `null` until set. Schema 6 (v1.7) |
| `meta.entry` | `'prd'\|'figma'` | — | intake provenance — `prd` (PRD/Q&A) or `figma` (`/pb:init --figma` resolved a frame). Defaults to `prd`. Schema 7 (v1.8) |
| `meta.overview` | `{ objectives, principles[] }` | Project Summary | from spec + constitution |
| `meta.userInsights` | `{ quantitative, researchSummary, executiveSummary }` | Project Summary | from `/pb:clarify` |
| `meta.others` | string \| null | — | **Retired (D-33).** Raw HTML, no schema, no writer, no check — the dump for terminology and business rules that had no home; those now have `content` and `ia.rules[]`. The sub-tab is gone; the field is kept in the registry per `AGENTS.md` §3 and removal waits for a major |
| `tokens{}` | a **W3C DTCG** document — `{ "<name>": { $value, $type } }` (flat or nested groups + `{alias}` refs) | all (CSS vars) | `pb/tools/tokens.py` (+ the shell's `pbResolveTokens`) resolves it → CSS custom properties on `:root`; `$type ∈ color\|dimension\|fontFamily\|fontWeight\|number\|duration\|shadow\|…` (space/size/radius/fontSize all → `dimension`) |
| `components[]` | organism objects | design-system site | the component library — shape below |
| `screens[]` | screen objects | Prototype | shape below |
| `staleness{}` | per-tab `{ lastSyncedPromptCount, currentPromptCount }` | — | **Deprecated** (D-19): nothing writes it, and the shell stopped reading it in v2.0.0 (D-29). Kept in the registry per `AGENTS.md` §3; removal waits for a major release |
| `flow{}` | `{ populated, mermaid, stories[], html? }` | UX Design | structured — shape below; `html` is legacy fallback only |
| `erd{}` | `{ populated, table[], mermaid, warnings[], html? }` | Data | structured — shape below; `html` is legacy fallback only |
| `ia.rules[]` | `{ id, title, kind, summary, decision?, implemented[], implementedBy[], readers[], displayedIn[], decidedIn, stateField?, states[].derived? }` + per-kind fields | UX Design → Logic | the declared business rules. **`decision{ question, options[], chose, why, status?, supersededOn?, affects? }`** is the record of how the rule got settled, on the rule itself (D-33) — `options[]` carries what LOST, the one thing a rule cannot say for itself, and `status: 'superseded'` dims the card in place. It renders for every kind; the retired `meta.tradeoffs[]` is migration 0010. **`stateField`** names the property that holds the state and opts the rule into the reachability check (D-31): a state neither assigned anywhere nor marked `derived: true` renders dashed, as one nothing can reach. Omit it and no claim is made. **Four kinds**, each with its own renderer: `decision` (title + summary + the decision block — a rule you have settled but not yet expressed as one of the three below; upgrading it later keeps the block) · `state-machine` (`states[]` + `transitions[][]` + `overlays[]` — an overlay is a condition that rides *on top of* whichever state you are in, drawn as a band spanning the states it covers) · `matrix` (`rows[]` × `cols[]`) · `constraint` (`invariants[]` = `{ must, enforcedBy, when, message? }` — for a rule that is neither a machine nor a table, e.g. "every weight pool totals 100%"; an invariant with no `enforcedBy` renders as a **warning**, because a stated rule nothing enforces is the finding). An unknown `kind` degrades to title + summary. `implementedBy[]` / `readers[]` / `enforcedBy` are function names resolved against the derived handler graph, so a rename in the code shows up as a dead link |
| `content{}` | `{ populated, terms[], strings[] }` | UX Design → Content | optional. `terms[]` = `{ id, term, en?, definition, aka[], avoid[], rule? }` — the glossary, where `avoid[]` is what the word is deliberately never called and `rule` points at an `ia.rules[].id`. `strings[]` = `{ key, text, kind, note? }` — the wording deck, `kind ∈ action\|status\|label\|title\|empty\|toast\|error` (an unknown kind keeps its own group rather than being dropped). **Both halves hand-authored**; no tool derives either, so the tab's only check is authored-vs-authored — a wording or a declared rule's state label that uses a banned word |

### `components[]` (one per reusable component)

Ported **verbatim** from the v0.4.0 `PB_DATA.handoff.organisms` shape:

```
{ id (kebab, unique), name, renderFn ("renderCmp{PascalCase}"), renderSrc ("render/components/<id>.js"),
  meta, scope ("global"|"local"),
  level ("atom"|"molecule"|"organism"), codeLayout ("stacked"|"side-by-side"),
  properties[], code{ lang, snippet }, anatomy (string | { renderProps, parts[] }), spec (string | { legend, renderProps, marginX, stack[] }),
  uiLogic[], usage{ demoProps, topics[], placement } }
```

- **`scope`** — `'global' | 'local'`. Drives the design-system site's **Global | Local** grouping. A component reads as
  global when `scope === 'global'` **or** a `dsMatch` exists; otherwise local.
- **`level`** — `'atom' | 'molecule' | 'organism' | 'template'` — the atomic-design layer. **Required**
  (schema 9; `lint_registry.py` R-LEVEL). Screens are implicitly `page`. The design-system site's Global/Local lists
  group components by level. **Component-first / atomic law (enforced, ERROR under `--strict`):** ONLY
  `level:atom` render bodies may emit raw HTML primitives; every molecule/organism/template/screen body is
  **pure composition** — layout containers + `pbUse('<child-id>', props)` calls to lower-level components
  (R-COMPOSE), whose set matches the declared `elements[]`/`anatomy.parts[]` orgIds (R-COMPOSE-MATCH), each
  composing strictly lower levels (R-LEVEL-ORDER). This is what lowers 1:1 to a Figma INSTANCE tree. A
  component that maps to a single DS component (`dsMatch`) is an `atom` even if visually composite.
- **`state` property convention** — if `properties[]` contains a property with `id: 'state'` (each option
  `{ label, value }`), it appears as a dropdown alongside the component's other enum properties; the design-system site
  demo shows **one live, interactive instance of the currently-selected variant** (changing any dropdown,
  including `state`, re-renders it). **Interactive components MUST declare it** (e.g. `default / error /
  disabled`, `default / loading / disabled`).
- **`anatomy` / `spec`** — either a **prose string** (rendered as a description beside a live preview) or a
  **structured object** (`anatomy.parts[]` / `spec.stack[]`) that drives the numbered redline annotations. The
  spec metadata carries whichever form is present (hand-off / bridge); author the structured object when you want measured
  redlines, the string when a plain description suffices.

Figma fields are recorded by `/pb:handoff` in `figma-transfer.json` (bridge mode: the
portable `dsKey` + `propertyMapping`; the `--mcp` legacy path also writes `figmaId`/`figmaComponentSetId`
back onto the registry). `dsMatch` may be authored to hint the DS component match.

### `screens[]` (one per screen)

```
{ id (kebab), name, renderFn, renderSrc ("render/screens/<id>.js"), layout{ type, gap, maxWidth, padding },
  elements[ { id, label, orgId, tokens[], sizing, state, uiLogic, bounds? } ], logicNotes[], figmaFrameId? }
```

#### Screen `render` bodies — the `data-*` interaction runtime

The Prototype tab is **interactive** (no screen-switcher). Screen/component render bodies emit `data-*`
attributes that a small declarative runtime in the shell wires up — clicking links/buttons moves between
screens, so the prototype is a real flow:

| Attribute | Effect |
|---|---|
| `data-nav="<screen-id>"` | navigate to that screen |
| `data-action="toggle-password"` | show/hide the password in its `.field` |
| `data-action="submit"` | validate the enclosing form's `.field__input`s, then on success run the `data-go`/`data-toast`/`data-redirect` below |
| `data-go="<screen-id>"` | (on a submit) navigate on success |
| `data-toast="<msg>"` | (on a submit) show a toast on success |
| `data-redirect="<screen-id>"` + `data-redirect-ms="<n>"` | (on a submit) auto-navigate after a delay |
| `data-required` · `data-validate="email"` · `data-minlength="<n>"` | per-input validation (on `.field__input`s) |

### Runtime-only — **NOT persisted to registry.json**

`handoff.view`, `handoff.selectedScreenId`, `handoff.selectedElementId`, `protoDevice`, `handoffScope`,
`erdView`, the flow side-tab, and the summary sub-tab are ephemeral UI state, rebuilt fresh from the
registry on each load and never written back. (This is why a click in the prototype never dirties
`registry.json`.)

### `flow` (UX Design tab — structured, trio-synced)

```
flow = { populated, mermaid, flows?: [ { name, mermaid } ],
         stories: [ { title, priority, jtbd, path, nodes?, scenarios[] } ],
         coverageWarnings?: [ { category, note, title?, status? } ], html? }
```

`/pb:plan --flow` writes `mermaid` (a `flowchart LR` source) + `stories[]`. The shell renders the canvas on
the **left** (it fills one viewport — no W×H controls) and a **User stories | Test cases** aside on the
right (each `scenarios[]` entry a checkbox), running Mermaid then re-routing every edge as straight
**orthogonal** connectors anchored at the nodes' 4 side-centers (Figma-board style)
and node colors matching the on-canvas legend (start/end black · decision yellow · input purple · action/
screen blue · subprocess grey — recolored by detected shape), plus a legend popover. `html` is a legacy pre-baked fallback used only when
`mermaid` is absent.

- **`path` / `nodes`** — each story declares the flow path it satisfies. `path` is the human string
  (`"Start → Login → Dashboard"`); **hovering a story highlights that path on the canvas** (matched nodes +
  connecting edges emphasized, the rest dimmed). The runtime resolves nodes by matching `path` tokens to the
  rendered node labels; `nodes` (an optional array of Mermaid node ids) makes the match exact when authored.
- **`flows`** — optional named flows for multi-flow projects; the canvas shows a dropdown to switch. When
  absent, the single `mermaid` is shown as one "Main flow".
- **`scenarios[]`** — a test case is either a plain string or `{ text, category }` where `category ∈
  ux | ui | function | business | system-edge` (the **QA lenses**). The Test cases panel tags each with a
  colored category chip; untagged strings render plain.
- **`coverageWarnings`** — `[{ category, note, title?, status? }]` (or plain strings) — edge cases the QA
  pass found that the UI/flow does **not** cover yet, listed as flagged rows in the same rhythm as the
  stories. **`status`** is `open` (default) · `resolved` · `accepted`; only `open` rides the warning rail
  and counts in the tab's gap tally, while settled ones stay visible below a divider — a fixed gap and an
  accepted one are both records worth keeping, but counting them as open makes the count a lie.

**Cards on the left, the case itself on the right.** A scenario and a gap note are both long-form on a
real project — 2,400 and 2,057 characters at the top end — so the Test Cases segment is a **master–detail
split**. Each test case is a **card**: the verdict glyph, the lens chip, the date, a two-line claim, and
one dim line saying what running it involves (`from quan-ly-chu-ky · 1 step · 4 expects · as hr`, or
*"No test block — verified by hand"*). Clicking a card opens the **detail panel at 50% width**; clicking
it again, or `Esc`, closes it.

**The two columns scroll independently.** Like the IA layout, this segment owns the viewport height
rather than sitting inside the page scroller, so each column has its own — reading a 2,400-character
case never drags the list you are working through out of view, and the panel's close button stays
pinned however far down you read. Below ~900px the split stacks into one column on the page's own
scroller, because two nested scrollers on a phone is worse than either.

The card's claim is the authored `title` when there is one, otherwise it is **derived**: the text's first
strong break (`— · . · : · ( · , · ;`) at least 24 characters in, capped at 110, never ending inside a
parenthesis. The minimum is what makes it a claim — breaking at the first delimiter yields *"Cổng trọng
số"* or *"Tình huống"*, fragments that identify nothing. The delimiters are punctuation rather than
words, so the rule holds in any language, and the claim is always a **prefix** of the authored text,
never a paraphrase.

**The panel is the only place the whole text appears, and it appears structured.** Three parts: the
verdict (story · verdict · detail · last run, with staleness spelled out), **How it runs** — the `test{}`
block said as sentences (`Click **[for="tdck-pop-probation"]**` · `The frame reads **"Chưa bắt đầu"**` ·
`No console error fires`), with the asserted value bold — and the author's own notes.

Those notes keep the structure the author already put there: newlines separate blocks, `·` opens a
bullet, backticks become code, `**…**` is honoured. Where a note has no newlines at all — all 22 on the
reference project — a block over 400 characters is broken where a sentence starts with an ALL-CAPS run,
because that is how this author marks a new thought (`CẬP NHẬT 2026-08-10`, `MỨC ĐỘ KIỂM:`). **Emphasis
is reported, never invented**: a run is bold because the author capitalised it. A single short caps word
is left alone — HR, KPI, UI and PRD are nouns, not shouting — and hyphen guards keep the rule out of
identifiers, so `T-ROLE-EL` is never rendered as T-**ROLE**-EL. On the reference project's longest note
that yields **9** bold runs in 2,057 characters.

### `erd` (Data tab — structured, trio-synced)

```
erd = { populated, table: [ { entity, field, type, example, notes } ], mermaid, warnings[],
        mock?: [ { entity, label, rows: [ { <field>: <value> } ] } ], html? }
```

`/pb:plan --data` writes `table[]` + `mermaid` (an `erDiagram` source). The shell is **single-column**: a
**Diagram | Table** toggle, with a relationship-legend popover (crow's-foot 1:1 / 1:N / N:N) on the diagram
and **data-set variant chips** on the table. Per-entity tables share fixed column widths so they line up.
`html` is a legacy pre-baked fallback used only when neither `mermaid` nor `table` is present.

- **`mock`** — optional sample row-sets per entity, surfaced as **per-table data-set variants** in the Table
  view: each entity table that has mock sets gets its own switcher (chips: `Schema` = the field/type/example
  definition, then one per `label`); a table with no mock sets shows no switcher. Selecting a variant swaps
  that table's Example column to the scenario's values (`rows[0]` is representative; an empty set reads as the
  no-data state). Use standard review scenarios — e.g. `New user`, `Empty`, `Returning`. Each set: `label` +
  `rows[]` (objects keyed by field names). Authored by `/pb:plan --data --mock`.

## The 4 tabs (prototype shell) + the design-system site

- **Prototype** — the live **interactive** app driven by the `data-*` runtime (above). Header-line tools (a
  **Browser | App** chrome toggle + an icon-only device switcher over 4 fixed sizes — monitor 1920×1080 /
  laptop 1280×832 / tablet 834×1112 / mobile 390×844, gated by `meta.devices`, default from `meta.device`)
  render the selected screen in a device frame that scales to fit. Browser chrome adds a tab strip +
  back/reload/URL bar; app chrome a titlebar (desktop) or a status bar (tablet/mobile). No screen-switcher.
- **Project Summary** — split: Overview / User Insights (the shared `meta-subtab` sub-tabs — and nothing else, D-33) in a scrolling
  left column, with a **scroll-spy table of contents** on the right that tracks the headings in view and
  navigates on click. One viewport, internal scroll.
- **UX Design** — five segments: **Logic** (declared rules + the derived ripple) · **Information Architecture**
  (job list over the derived site map) · **User Flow** (the wireflow from `flow.mermaid`, filling one viewport,
  with the user stories beside it — hovering a story highlights the path it satisfies) · **Test Cases** ·
  **Content** (the `content` glossary + wording deck, above).
- **Data** — single-column **Diagram | Table** toggle over `erd` (above): relationship-legend popover on the
  diagram, data-set variant chips on the aligned tables.

**Design-system site** (`design-system.html`, served at `/design-system` — a second projection of the same
registry, not a tab): every component auto-collected, grouped by `scope` → atomic `level`. Each
**interactive** component (auto-detected — a `state` property OR body `data-*`/`onclick`/control tags) gets a
**live, clickable demo**; **all** get a **variant grid** (the cartesian product of enum `properties`) + a
**Push to Figma** bridge node-JSON snippet (paste into the plugin's *Code → Figma* tab). Token foundations
render as swatches. Same `renderCmp*` functions the prototype uses (shared `pb/template/runtime.js`) — never
duplicated.

## Render-function inventory

_(Phase 3)_ — the **prototype** shell: `render`, `renderMetaNav`, `renderMetaPanel`, `renderPrototype`,
`renderMetaSummary` (+ `pbRenderOverview/UserInsights`), `renderMetaFlow`/`renderFlowPopulated`,
`renderMetaERD`/`renderERDPopulated`. (The former UI Design `renderHandoff*` cluster is retired with the tab.)
The **design-system** site (`design-system.html`) has its own workbench builder (`buildDS` → the interactive
demo + variant-grid enumerator + push dialog). Both sites share `pb/template/runtime.js` and the per-component
`renderCmp*` / per-screen `renderScreen*` bodies, generated from the registry by `render.py` (`--ds` for the DS site).

## Sync rules

A component edit re-renders **both sites** on `/pb:build` (the prototype's composed screens + the
design-system site) — they're two projections of the one `registry.json`, never separately maintained.
Flow and Data **ride the trio**: every trio-touching `/pb:build` reconciles `flow` and `erd` in the same
turn — a new screen gains a node and a story, a removed one loses them, a new data-bearing field gains an
`erd.table[]` row. The reconcile **inserts and repairs; it never re-authors** — first-time population, the
five-lens QA pass and any restructuring stay with `/pb:plan --flow` and `/pb:plan --data`. Canonical rule: `CLAUDE.md`
§ *Auto-sync*. _(folded from the v0.4.0 hooks: Phase 4–5)_

## Test plans — a run is planned, then delegated

`/pb:test` does not start by testing. It first writes `memory/test-plans/<YYYY-MM-DD-HHMMSS>.md`, the
**plan of record** for that run: one item per test case, each item one binary question. The question
belongs to the **lane**, stated once in its heading, so items are rows rather than repeated sentences.

```markdown
## R · Roles
**Did exactly the declared roles reach it — no more, no fewer?**

| # | Gated item | Declared | Answer | Evidence |
|---|---|---|---|---|
| R4 | screen `hieu-suat-phong-ban` | manager, hr | | |
```

`#` is a lane letter plus a number (`F` functional · `H` freshness · `R` roles · `S` server ·
`X` security · `D` drift · `C` coherence); a lane adds a data column only where a row must be
self-contained (the recorded digests for `H`, the declared roles for `R`). The question is admissible
only if it opens
*Does/Did/Is/Are/Was*, names the single observation that settles it, needs nothing from `memory/spec.md`
or the conversation to answer, and is phrased so **`yes` means the check held** — uniform polarity is
what lets a plan be tallied mechanically. Anything answerable *it depends*, anything asking whether
coverage is *sufficient*, anything asking for a rating or a recommendation is an **open question** and is
rewritten or dropped. A check that cannot be phrased this way contributes no item: project health ranks
rather than judges, so it has none.

The items then go to `pb-tester` subagents on **sonnet** — one per lane, ≤25 items each, ≤8 agents —
holding the plan path, the registry, the preview URL and their lane's command. They are given no spec, no
plan, no decisions log, no prior `lastResult` and no framing from the session that authored the design,
because a grader that knows the intent grades the intent. Each returns `<id> · yes | no | blocked ·
<evidence>` rows and nothing else; **`blocked`** is the absence of an answer (never a pass), and evidence
is mandatory even on a `yes` — one line, the observation, never a narrative.

The coordinator fills the rows back into the plan file in place and reconciles every id — it may not drop
one, may not re-word one, and may not overturn a `no` except by dispatching a fresh agent and showing
both rows. **The chat gets the short form**: a header, one line per `no` or `blocked`, and the verdict
`<N> items · <Y> held · <Z> failed · <B> blocked`. Held items are the count and the file, not 38 printed
successes. Vocabulary: `sandbox-test`. Canonical rule: `pb/commands/test.md` §2a–§2b, §11.

## Component governance

_(Phase 5)_ — DS-first, Local-first (R0); extend with a variant before spawning (R2); auto-layout
on every Figma frame (R3); kebab-case non-colliding IDs (R4); the naming contract.

## Export tiers — JSX/TSX component export (v1.7)

Three tiers via `/pb:handoff --tier=…`:

- **`host`** — the runnable single-file `prototype.html` (`/pb:handoff --tier=host`). Not reusable components.
- **`scaffold`** *(shipped v1.7)* — `render_react.py` deterministically emits a **React + Vite** app:
  one wrapper component per registry component/screen (reusing its render body), tokens as CSS vars +
  a Tailwind theme. Runs + lints; **mechanical** (wrappers), not idiomatic JSX (NS9).
- **`hardened`** *(deferred)* — idiomatic per-component Tailwind JSX, MCP-resolved against the real DS,
  repo-matched, `validate_code`-scored, `pb-reviewer` + human approved. Needs the G-B decision,
  `pb-full-picture.md`'s export contracts, and the DS-MCP path before it's built.

**Pre-registered success criterion for the hardened tier:** a front-end engineer integrates **≥ 1
exported component** into a fresh Vite app and renders it correctly in **< 30 minutes**, using only the
generated files + a short README. That is the gate the hardened tier must clear.
