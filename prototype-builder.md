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
tokens are applied to the **product subtree** (`.pb-product`) at boot via `applyRegistryTokens` — never onto `:root`,
which holds the tool's own `--pb-*` vocabulary (`pb/template/chrome.css`).

**Responsive styles (`styleSrc`).** An inline `style=""` cannot hold a breakpoint, so a component or
screen that changes across device sizes carries an optional `styleSrc` → `render/styles/<id>.css`.
`render.py` emits `pb/template/product.css` (the size-class utilities) and then every sheet, components
before screens, into one `<style id="pb-product-css">` in both sites and in the React scaffold. A sheet
styles its own root class — `.c-<id>` for a component, `.s-<id>` for a screen — and uses
**`@container pb-screen (min-width: …)`, never `@media`**: the device frames are `<div>`s in one
document, so `@media` answers the browser window, not the frame. Size classes: **compact** < 600px
(mobile) · **medium** 600–1023px (tablet) · **expanded** ≥ 1024px (laptop, monitor). Utilities:
`r-compact` · `r-medium-up` · `r-expanded-up` · `r-below-expanded` (show only in that range) and
`r-cols` (1 → 2 → 3 columns). Anything that changes across sizes lives in the sheet, not inline —
an inline declaration beats the container rule. Lint: `R-STYLESRC` · `R-STYLE-MEDIA` · `R-STYLE-SCOPE`
· `R-HEX`/`R-PX` · `R-RESPONSIVE` (see `meta.responsive`).

### Top-level shape

| Key | Type | Feeds | Notes |
|---|---|---|---|
| `meta.name` | string | — | project name |
| `meta.shell` | `'browser'\|'app'` | Prototype | default preview chrome — `browser` (tab strip + back/reload/URL bar) or `app` (plain titlebar on desktop; a contrast-aware device status bar on tablet/mobile). Viewer can toggle live; set at `/pb:init`. Defaults to `'browser'` |
| `meta.device` | `'monitor'\|'laptop'\|'tablet'\|'mobile'` | Prototype | default device for the preview frame; set at `/pb:init`. Falls back to `'laptop'`. Legacy `'desktop'` → `'laptop'` |
| `meta.devices` | `('monitor'\|'laptop'\|'tablet'\|'mobile')[]` | Prototype | the fixed sizes this project supports (`monitor 1920×1080 · laptop 1280×832 · tablet 834×1112 · mobile 429×926`) — unsupported sizes are disabled in the switcher. Optional; defaults to all four. Legacy `'desktop'` expands to `monitor`+`laptop` |
| `meta.responsive` | `true\|false\|null` | Prototype · build · lint | whether the UI **adapts** across the `meta.devices` size classes — asked at `/pb:init` right after the device question. `true`: every screen answers at every listed size (container queries via `styleSrc` or the `r-*` utilities; `R-RESPONSIVE` warns per screen that nothing adapts). `false`: one layout — `meta.devices` is trimmed to `meta.device`. `null` (an older project): `/pb:build` asks once before its next screen/component write; lint stays silent on it. Additive, no schema bump |
| `meta.designSystem` | `{ name, designLink, codeLibrary, linked }` | design-system site | the linked design system — `name`, `designLink` (the project's Figma file), `codeLibrary` (folder path or repo URL). Seeded from the DS Lock at `/pb:init`. **Editable in the Project settings dialog**, saved through `POST /api/meta` on `/pb:preview` (read-only over `file://`): **`name` is required**; `designLink` is optional and, when set, must be a `figma.com/file/…` or `figma.com/design/…` link — except that a non-Figma link the project already carries is **kept with a warning** rather than blocking a save of the names. Hand-off, the Figma push and the drift check read it. Absent → Project settings shows it empty |
| `meta.platform` | `'web'\|'ios'\|'android'\|'desktop'` | — | the DS/target platform; set at `/pb:init`. Defaults to `'web'`. Schema 5 (v1.6) |
| `meta.dsSource` | `{ type, ref, clonedAt } \| null` | — | provenance of the cloned DS: `type ∈ figma\|code-library\|mcp\|common`, `ref` the literal URL/path/name, `clonedAt` ISO stamp. `null` until `/pb:pull-ds` clones. The full token/component snapshot lives in `design-system/<name>/.source.json`; `/pb:test --drift` §5 diffs the live source against it. Schema 5 (v1.6) |
| `meta.outputTier` | `'host'\|'scaffold'\|'hardened'` | — | which export tier `/pb:handoff` targets. `host` = the runnable single-file prototype; `scaffold` = deterministic React+Tailwind (`render_react.py`); `hardened` = idiomatic/DS-integrated (deferred). Defaults to `host`. Schema 6 (v1.7) |
| `meta.exportTarget` | string \| null | — | machine-readable export target mirroring the Stack Lock (e.g. `'react-tailwind'`); `null` until set. Schema 6 (v1.7) |
| `meta.entry` | `'prd'\|'figma'` | — | intake provenance — `prd` (PRD/Q&A) or `figma` (`/pb:init --figma` resolved a frame). Defaults to `prd`. Schema 7 (v1.8) |
| `meta.overview` | `{ objectives, principles[] }` | Project Summary | from spec + constitution |
| `meta.userInsights` | `{ quantitative, researchSummary, executiveSummary }` | Project Summary | from `/pb:clarify` |
| `meta.others` | string \| null | — | **Retired (D-33).** Raw HTML, no schema, no writer, no check — the dump for terminology and business rules that had no home; those now have `content` and `ia.rules[]`. The sub-tab is gone; the field is kept in the registry per `AGENTS.md` §3 and removal waits for a major |
| `tokens{}` | a **W3C DTCG** document — `{ "<name>": { $value, $type } }` (flat or nested groups + `{alias}` refs) | all (CSS vars) | `pb/tools/tokens.py` (+ the shell's `pbResolveTokens`) resolves it → CSS custom properties scoped to `.pb-product` (and published as `--prj-<name>` on `:root` for a deliberate opt-in); `$type ∈ color\|dimension\|fontFamily\|fontWeight\|number\|duration\|shadow\|…` (space/size/radius/fontSize all → `dimension`) |
| `components[]` | organism objects | design-system site | the component library — shape below |
| `screens[]` | screen objects | Prototype | shape below |
| `staleness{}` | per-tab `{ lastSyncedPromptCount, currentPromptCount }` | — | **Deprecated** (D-19): nothing writes it, and the shell stopped reading it in v2.0.0 (D-29). Kept in the registry per `AGENTS.md` §3; removal waits for a major release |
| `flow{}` | `{ populated, mermaid, stories[], html? }` | UX Design | structured — shape below; `html` is legacy fallback only |
| `erd{}` | `{ populated, table[], mermaid, warnings[], html? }` | Data | structured — shape below; `html` is legacy fallback only |
| `ia.jobs[]` | `{ id, roles[], priority, when, want, so, screens[], source? }` | UX Design → Information Architecture | what each role needs done, read back as *When …, I want to …, so I can …*. Written by `/pb:clarify` §1b and approved at G-JTBD (seeded optionally at `/pb:init`); `screens[]` filled by `/pb:clarify` §1c (G-IA promote, `explore.py promote`); `/pb:plan --ia <job> --into <screen>` for a late job. A job with no screen is flagged unhandled |
| `ia.layers[]` | `{ depth: number \| 'overlay', name, purpose }` | UX Design → Information Architecture | one sentence of purpose per navigation layer, written by `/pb:clarify` §1c (G-IA promote) from the chosen grouping. Membership, edges and overlays are **derived**, never stored |
| `meta.navHub` | string \| string[] | Information Architecture site map | the component id(s) holding the top-level navigation — a sidebar, a bottom tab bar, or both (v2.1.0, additive). The site map's layer 0 is read from its nav items (any object literal with a `label` and a `key`/`screen`/`to`); absent, a body named `sidebar.js` is used, and with neither the map renders an empty state saying why. Set by `/pb:clarify` §1c (G-IA promote, when the chosen grouping names its hub component) |
| `ia.rules[]` | `{ id, title, kind, summary, decision?, implemented[], implementedBy[], readers[], displayedIn[], decidedIn, stateField?, states[].derived? }` + per-kind fields | UX Design → Logic | the declared business rules. **`decision{ question, options[], chose, why, status?, supersededOn?, affects? }`** is the record of how the rule got settled, on the rule itself (D-33) — `options[]` carries what LOST, the one thing a rule cannot say for itself, and `status: 'superseded'` dims the card in place. It renders for every kind; the retired `meta.tradeoffs[]` is migration 0010. **`stateField`** names the property that holds the state and opts the rule into the reachability check (D-31): a state neither assigned anywhere nor marked `derived: true` renders dashed, as one nothing can reach. Omit it and no claim is made. **Four kinds**, each with its own renderer: `decision` (title + summary + the decision block — a rule you have settled but not yet expressed as one of the three below; upgrading it later keeps the block) · `state-machine` (`states[]` + `transitions[][]` + `overlays[]` — an overlay is a condition that rides *on top of* whichever state you are in, drawn as a band spanning the states it covers) · `matrix` (`rows[]` × `cols[]`) · `constraint` (`invariants[]` = `{ must, enforcedBy, when, message? }` — for a rule that is neither a machine nor a table, e.g. "every weight pool totals 100%"; an invariant with no `enforcedBy` renders as a **warning**, because a stated rule nothing enforces is the finding). An unknown `kind` degrades to title + summary. **`blocks[]` (v2.1.0, additive, any kind)** — an ordered list of typed blocks that carry the rule's structure instead of prose, one renderer each: `cases` (`rows[{when, then, tone?}]`, `inputs?[]`, `else?`) · `scope` (`acts[]`, `untouched[]`) · `placement` (`surfaces[{surface, holds[], never?[]}]`) · `matrix` (`rowLabel, rows[], cols[], cells`) · `validation` (`items[{must, enforcedBy?\|enforcedIn?, when?, message?, code?}]`) · `formula` (`expr`, `terms[{name, means}]`, `example?`) · `steps` (`items[{label, detail?}]`) · `params` (`items[{name, value, unit?, note?}]`) · `effects` (`writes[]`, `ripple[{screen, shows}]`) · `note` (`text`). `logic_check.py` L-BLOCK checks each against the renderer. `summary` is a one-line lead; the decision folds away when blocks exist, and lineage fields (`supersedes`, `supersededBy`, `amended*`, `was`, `derivedFrom`, `origin`, `citeNote`, `retired[]`, …) render in one *History & sources* fold — `stillOpen` stays visible as an *open* chip. `invariants[]` render on any kind and accept `enforcedIn` (a location) beside `enforcedBy` (a handler). `implementedBy[]` / `readers[]` / `enforcedBy` are function names resolved against the derived handler graph, so a rename in the code shows up as a dead link |
| `content{}` | `{ populated, terms[], strings[] }` | UX Design → Content | optional. `terms[]` = `{ id, term, en?, definition, aka[], avoid[], rule? }` — the glossary, where `avoid[]` is what the word is deliberately never called and `rule` points at an `ia.rules[].id`. `strings[]` = `{ key, text, kind, note? }` — the wording deck, `kind ∈ action\|status\|label\|title\|empty\|toast\|error` (an unknown kind keeps its own group rather than being dropped). **Both halves hand-authored**; no tool derives either, so the tab's only check is authored-vs-authored — a wording or a declared rule's state label that uses a banned word |

### `components[]` (one per reusable component)

Ported **verbatim** from the v0.4.0 `PB_DATA.handoff.organisms` shape:

```
{ id (kebab, unique), name, renderFn ("renderCmp{PascalCase}"), renderSrc ("render/components/<id>.js"),
  styleSrc? ("render/styles/<id>.css" — responsive rules, root class .c-<id>),
  meta, scope ("global"|"local"),
  level ("atom"|"molecule"|"organism"), codeLayout ("stacked"|"side-by-side"),
  properties[], code{ lang, snippet }, specSrc ("spec/components/<id>.json" — anatomy, layout, elements, shape,
  measured, anatomyNote?, specNote?, legacy?), uiLogic[], usage{ example, demoProps, topics[], placement } }
```

- **`scope`** — `'global' | 'local'`. Drives the design-system site's **Local / Library** badge (every component carries
  exactly one). A component reads as a library component when `scope === 'global'` **or** a `dsMatch` exists; otherwise
  it is local.
- **`level`** — `'atom' | 'molecule' | 'organism' | 'template'` — the atomic-design layer. **Required**
  (schema 9; `lint_registry.py` R-LEVEL). Screens are implicitly `page`. The design-system site lists molecules,
  organisms and templates (an atom only as a part inside its parent — unless it is card-shaped, `shape: "card"`, and
  then it is listed as a **Card**). **Component-first / atomic law (enforced, ERROR under `--strict`):** ONLY
  `level:atom` render bodies may emit raw HTML primitives; every molecule/organism/template/screen body is
  **pure composition** — layout containers + `pbUse('<child-id>', props)` calls to lower-level components
  (R-COMPOSE), whose set matches the declared screen `elements[]` orgIds and a component's `instance` parts (`anatomy` `instanceOf`; R-COMPOSE-MATCH), each
  composing strictly lower levels (R-LEVEL-ORDER). This is what lowers 1:1 to a Figma INSTANCE tree. A
  component that maps to a single DS component (`dsMatch`) is an `atom` even if visually composite.
- **`state` property convention** — if `properties[]` contains a property with `id: 'state'` (each option
  `{ label, value }`), it appears as a dropdown alongside the component's other enum properties; the design-system site
  demo shows **one live, interactive instance of the currently-selected variant** (changing any dropdown,
  including `state`, re-renders it). **Interactive components MUST declare it** (e.g. `default / error /
  disabled`, `default / loading / disabled`).
- **The spec sidecar** (`spec/components/<id>.json`, via `specSrc`; **schema 13** — `CURRENT_SCHEMA` in
  `pb/migrations/manifest.py`). Anatomy and spec are **measured, not typed**, in the Specs plugin's shape
  (specsplugin.com/schema): `tools/spec_measure.py` renders the component with its demo props
  (`properties[].default`, then `usage.example`) and writes, beside the hand-authored keys (`usage`, `uiLogic`, `code`):
  ```
  anatomy:  { <part>: { type: text|glyph|vector|container|slot|instance, instanceOf? } }   // instanceOf = a registry id
  layout:   [ { "root": [ <part> | { <part>: [ … ] } ] } ]                                 // the part tree, in DOM order
  elements: { <part>: { parent, anchor?, visibleWhen?{ prop, is: "set"|"true" },
                        styles?{ padding{top,right,bottom,left, token | tokens{side}},
                                 margin{top,right,bottom,left — px, or "auto" for a side set to auto; token | tokens{side}},
                                 itemSpacing{value | "auto", direction, via: gap|margin|gap+margin|layout|none|space-*, token?, min?},
                                 cornerRadius{value, token?}, backgroundColor{value, token?}, textColor{value | "inherit", token?} } } }
  shape:    "card"            // a painted root (an opaque fill, a radius > 0 and padding > 0) that is not a native
                              // control element (<button>/<a>/<input>/<select>/<textarea>; a role=button div still
                              // counts) and has ≥ 2 non-root parts; absent otherwise
  measured: { at, by: "spec_measure.py", props }
  ```
  Parts come from `data-part="<name>"` in the render body (the root is `data-part="root"`); a `pbUse` child is an
  `instance` part named after its id (`-1…-n` when repeated). **A part is optional iff it carries `visibleWhen`** —
  derived by re-rendering with each prop unset, never typed. A `token` is filled only when the measured value equals
  a registry token's resolved value; otherwise the raw value stands alone. **Margin is recorded like padding** — four
  sides, a side set to `auto` kept as the keyword (never as the pixels it resolved to), and `token` (all four equal
  and a token) or per-side `tokens`. `/pb:build` §3a re-measures a component
  when it is built or changed; never hand-edit the five measured keys. Schema-12 prose `anatomy`/`spec` strings
  live on as `anatomyNote`/`specNote`, and a structured `anatomy.parts[]`/`spec.stack[]` as `legacy` (migration `0011`).

Figma fields are recorded by `/pb:handoff` in `figma-transfer.json` (bridge mode: the
portable `dsKey` + `propertyMapping`; the `--mcp` legacy path also writes `figmaId`/`figmaComponentSetId`
back onto the registry). `dsMatch` may be authored to hint the DS component match.

### `screens[]` (one per screen)

```
{ id (kebab), name, renderFn, renderSrc ("render/screens/<id>.js"), styleSrc? ("render/styles/<id>.css", root class .s-<id>),
  layout{ type, gap, maxWidth, padding },
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

- **Prototype** — the live **interactive** app driven by the `data-*` runtime (above). Every control lives in the
  **Sandbox inspector** — a right-hand panel opened by the bar's hourglass or `S` (Esc closes it unless pinned; the pin
  docks it and pushes the stage). **Conditions**: a **Browser | App | None** chrome toggle, an icon-only device
  switcher over 4 fixed sizes (monitor 1920×1080 / laptop 1280×832 / tablet 834×1112 / mobile 429×926, gated by
  `meta.devices`, default from `meta.device`), Compare, the Structure tree and the role. **Run**: the runnable `test{}`
  scenarios grouped by story, run in the page. **Explore**: the open `/pb:explore` round. **Reset session** in the
  footer. Phone and tablet frames scale to fit whole (32px inset, 24px under 900px tall). Browser chrome adds a tab
  strip + back/reload/URL bar; app chrome a titlebar (desktop) or a status bar (tablet/mobile). No screen-switcher.
- **The bar** — the project button (name → **Project settings**: project name, design-system name (required), Figma
  file (optional), theme System / Light / Dark) and **⌘K** global search. Settings are saved by `POST /api/meta` on
  `/pb:preview`; over `file://` they are read-only.
- **Project Summary** — split: Overview / User Insights (the shared `meta-subtab` sub-tabs — and nothing else, D-33) in a scrolling
  left column, with a **scroll-spy table of contents** on the right that tracks the headings in view and
  navigates on click — shown only when the content has ≥ 3 headings. One viewport, internal scroll. Prose is **rich
  text** (below): the objective is a lead paragraph, principles a numbered list.
- **UX Design** — five segments: **Logic** (declared rules + the derived ripple) · **Information Architecture**
  (the derived site map over the job list, one filter bar above both) · **User Flow** (the wireflow from `flow.mermaid`, filling one viewport,
  with the user stories beside it — hovering a story highlights the path it satisfies) · **Test Cases** ·
  **Content** (the `content` glossary + wording deck, above).
- **Data** — single-column **Diagram | Table** toggle over `erd` (above): relationship-legend popover on the
  diagram, data-set variant chips on the aligned tables.

**Design-system site** (`design-system.html`, served at `/design-system` — a second projection of the same
registry, not a tab): every component is auto-collected and **every listed component gets a live, clickable demo**
(the same `renderCmp*` functions the prototype uses, from the shared `pb/template/runtime.js` — never duplicated).
Token foundations render as swatches, one page per kind. It is a docs site: a tree whose roots are **Components** and
**Foundations** (plain labels — no counts, nothing to expand — and a filter), listing molecules, organisms and
templates plus card-shaped atoms (**Card**), each row with its level and a **Local / Library** badge; atoms appear
only as parts inside a parent. One page at a time by hash (`#/c/<id>`, `#/f/<kind>`). A component page is a
`pbHeadHTML` head (no description) over **Overview** — a workbench: variant and device pickers, **Layers** (Anatomy ·
Spec with Margin / Padding / Gap colours and hover/focus/tap labels), a Code view (HTML | CSS), *Edit props* (closed),
*Tokens used*, *Used in*, *Source* and the closed *Design notes* — and the tabs **Variants & spec** (per-variant
spec) and **Anatomy** (parts table, copyable token chips, instance tokens). **Push to Figma** is **Copy JSON** (the
bridge node JSON for the plugin's *Code → Figma* tab) or **Copy prompt**
(`/pb:handoff --mode=3 --scope=components --component <id>` plus the project's Figma file). Themed like the
prototype (System / Light / Dark); the demo stages stay light.

## Rich text

Prose a person reads on a page — the Project Summary (`meta.overview.objectives`, principle bodies,
`meta.userInsights.*`), an IA job's `gap` note, a component's design notes (`purpose`) — is rendered by
`pbRichText(str)` in `runtime.js` (both shells). It **escapes first**, then reads a small set of marks, so an author
(or `/pb:clarify`) can give a long text a hierarchy without markup of their own:

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

An unbalanced mark stays literal; `{inline:true}` returns the marks only, with no blocks. The colours are the tool's
`--pb-pass` / `--pb-fail` tokens, so they follow the theme. The marks are authored, never inferred: the
writer agents add them under the limits in `pb/commands/clarify.md`.

## Render-function inventory

_(Phase 3)_ — the **prototype** shell: `render`, `renderMetaNav`, `renderMetaPanel`, `renderPrototype`,
`renderMetaSummary` (+ `pbRenderOverview/UserInsights`), `renderMetaFlow`/`renderFlowPopulated`,
`renderMetaERD`/`renderERDPopulated`. (The former UI Design `renderHandoff*` cluster is retired with the tab.) `renderPrototype()` repaints only when the Prototype tab is the open one; called while another tab is open (a render body's script `onerror`, a timer, a store subscriber) it just marks the prototype dirty, and the next switch back repaints it — it never overwrites the page the reader is on.
The **design-system** site (`design-system.html`) has its own workbench builder (`buildDS` → the Overview
workbench (`showOverview`), the Variants & spec and Anatomy tabs, and the push dialog (`openPush`); `buildNav` + `route` for the tree and the per-page hash routing). Both sites share `pb/template/runtime.js` and the per-component
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

## Footprint — what pb starts, and what it leaves behind (v2.2)

Browsers, servers and the files a project grows are bounded by four tools and one report. All are
stdlib; Playwright stays a lazy, optional import. Canonical rules: `CLAUDE.md` § *pb bounds its own
footprint*; the design reason is `DESIGN.md` **I-10**.

| Tool | What it does |
|---|---|
| `tools/browser.py` | The one door a headless browser opens through: `browser_slot(who)` · `open_browser(p, who)` · `find_preview(registry)`. A counting semaphore of `slot-<i>.lock` files in `<tmp>/pb-browser-slots-<uid>/` (mode 0700; the kernel frees a slot when its holder dies). Limit `PB_BROWSER_SLOTS` (default **3**, `0` = none); `PB_BROWSER_WAIT` (default 120 s) after which it **fails open** with a `note:`; `PB_BROWSER_TRACE` (a file, one line per launch) |
| `tools/test_run.py` | Transport: this project's running preview when there is one (`reusing the running preview at <url>`), else a private server for the run; `--isolated` forces the private one, `--attach [URL]` is explicit. `--all` = functional + roles + server in one process, one browser, a fresh context per mode; worst exit code; `--json` → `{"mode": "all", "modes": {…}}` |
| `tools/shot.py` | `shot.py [registry.json] (--screen ID \| --path /explore/<id>/<slot> \| --url http://127.0.0.1:…) [--viewport WxH]… [--full-page] [--selector CSS] [--click CSS]… [--wait-for CSS] [--wait MS] [--role ID] [--eval JS] [--console] [--out FILE_OR_DIR] [--isolated]`. Default 1440x900 and 390x844 → `.preview/shots/<name>-<WxH>.png`. Exit 0 ok · 1 console errors / something not found · 2 usage · 3 cannot run |
| `tools/serve.py` | The preview server. `--idle-exit MINUTES` (default 30, `0` = never; `PB_PREVIEW_IDLE_MIN`) · `--debounce-ms N` (default 300) · `--status` / `--stop` (`--json`). `/__pb_health` adds `clients`, `idleSeconds`, `startedAt`. Polls every 0.3 s while a tab is open or a request came in the last minute, every 2 s otherwise; a page request checks the files first |
| `tools/explore.py` | `list` adds each open round's age and `STALE` (`--stale-days`, default 3; `--json` adds `ageDays`, `stale`); `promote` / `reject` report `stillOpen`; `check --shots` launches through `browser.py`; `server.log` is trimmed to its last 256 KB when over 1 MB |
| `tools/clean.py` | `/pb:clean`. Dry run by default; bare `--apply` = orphan `render/_candidates/` folders, an over-1 MB `server.log`, `.preview/shots/`; `--keep-backups N` (in each of `memory/backups/` and `.pb-backups/`) and `--keep-closed N` are the only deletion of a backup or a closed round. Never an open round, never a server |
| `lint_registry.py --report` | A `resources` block (largest key, backups, open and closed rounds, `server.log`, orphan candidates, the preview server); thresholds `backups_mb` 50 · `backups_count` 20 · `explore_open_days` 3 · `explore_closed_mb` 50 · `server_log_kb` 1024 · `registry_key_share` 0.35 · `preview_idle_min` 60, overridable in `memory/doctor.json`. Ranks, never gates |

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
