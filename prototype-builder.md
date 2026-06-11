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
`renderSrc` wins when both are present, and `check.py` warns to remove the inline copy.) Design
tokens are applied onto `:root` at boot via `applyRegistryTokens`.

### Top-level shape

| Key | Type | Feeds | Notes |
|---|---|---|---|
| `meta.name` | string | — | project name |
| `meta.shell` | `'browser'\|'app'` | Prototype | default preview chrome — `browser` (tab strip + back/reload/URL bar) or `app` (plain titlebar on desktop; a contrast-aware device status bar on tablet/mobile). Viewer can toggle live; set at `/pb:init`. Defaults to `'browser'` |
| `meta.device` | `'monitor'\|'laptop'\|'tablet'\|'mobile'` | Prototype | default device for the preview frame; set at `/pb:init`. Falls back to `'laptop'`. Legacy `'desktop'` → `'laptop'` |
| `meta.devices` | `('monitor'\|'laptop'\|'tablet'\|'mobile')[]` | Prototype | the fixed sizes this project supports (`monitor 1920×1080 · laptop 1280×832 · tablet 834×1112 · mobile 390×844`) — unsupported sizes are disabled in the switcher. Optional; defaults to all four. Legacy `'desktop'` expands to `monitor`+`laptop` |
| `meta.designSystem` | `{ name, designLink, codeLibrary, linked }` | UI Design | the linked design system — `designLink` (Figma/doc URL), `codeLibrary` (folder path or repo URL). Seeded from the DS Lock at `/pb:init`. Optional/tolerated-absent → the DS bar shows an "add one" affordance |
| `meta.overview` | `{ objectives, principles[] }` | Project Summary | from spec + constitution |
| `meta.userInsights` | `{ quantitative, researchSummary, executiveSummary }` | Project Summary | from `/pb:clarify` |
| `meta.tradeoffs[]` | `[{ title, question, options, decision, why, tabsAffected }]` | Project Summary | UI Logic Trade-offs |
| `meta.others` | string \| null | Project Summary | freeform |
| `tokens{}` | `{ "<name>": { value, kind } }` | all (CSS vars) | injected onto `:root`; `kind ∈ color\|radius\|space\|size\|type\|shadow\|alias` |
| `components[]` | organism objects | UI Design · component | the component library — shape below |
| `screens[]` | screen objects | Prototype + UI Design · screen | shape below |
| `staleness{}` | per-tab `{ lastSyncedPromptCount, currentPromptCount }` | flow / handoff / erd badges | |
| `flow{}` | `{ populated, mermaid, stories[], html? }` | UX Design | structured — shape below; `html` is legacy fallback only |
| `erd{}` | `{ populated, table[], mermaid, warnings[], html? }` | Data | structured — shape below; `html` is legacy fallback only |

### `components[]` (one per reusable component)

Ported **verbatim** from the v0.4.0 `PB_DATA.handoff.organisms` shape:

```
{ id (kebab, unique), name, renderFn ("renderCmp{PascalCase}"), renderSrc ("render/components/<id>.js"),
  meta, scope ("global"|"local"),
  level ("atom"|"molecule"|"organism"), codeLayout ("stacked"|"side-by-side"),
  properties[], code{ lang, snippet }, anatomy (string | { renderProps, parts[] }), spec (string | { legend, renderProps, marginX, stack[] }),
  uiLogic[], usage{ demoProps, topics[], placement } }
```

- **`scope`** — `'global' | 'local'`. Drives the UI Design **Global | Local** sub-tabs. A component reads as
  global when `scope === 'global'` **or** a `dsMatch` exists; otherwise local.
- **`level`** — `'atom' | 'molecule' | 'organism'` — the atomic-design layer. Optional; when present, the UI
  Design Global/Local lists group components by level (atoms → molecules → organisms). Compose upward:
  atoms into molecules, molecules into organisms, organisms onto screens — never inline a one-off (see the
  atomic-composition principle in `constitution.md`).
- **`state` property convention** — if `properties[]` contains a property with `id: 'state'` (each option
  `{ label, value }`), it appears as a dropdown alongside the component's other enum properties; the UI Design
  demo shows **one live, interactive instance of the currently-selected variant** (changing any dropdown,
  including `state`, re-renders it). **Interactive components MUST declare it** (e.g. `default / error /
  disabled`, `default / loading / disabled`).
- **`anatomy` / `spec`** — either a **prose string** (rendered as a description beside a live preview) or a
  **structured object** (`anatomy.parts[]` / `spec.stack[]`) that drives the numbered redline annotations. The
  UI Design drawer renders whichever form is present; author the structured object when you want measured
  redlines, the string when a plain description suffices.

Figma fields (`figmaId`, `figmaComponentSetId`, `dsMatch`) are added by `/pb:build-figma-handoff`.
`token.kind ∈ color | radius | space | size | type`.

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

### `flow` (UX Design tab — structured, decoupled)

```
flow = { populated, mermaid, flows?: [ { name, mermaid } ],
         stories: [ { title, priority, jtbd, path, nodes?, scenarios[] } ],
         coverageWarnings?: [ { category, note } ], html? }
```

`/pb:sync-flow` writes `mermaid` (a `flowchart LR` source) + `stories[]`. The shell renders the canvas on
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
- **`coverageWarnings`** — `[{ category, note }]` (or plain strings) — edge cases the QA pass found that the
  UI/flow does **not** cover yet. Rendered as a "Coverage gaps" callout above the test checklist so the user
  sees what's missing.

### `erd` (Data tab — structured, decoupled)

```
erd = { populated, table: [ { entity, field, type, example, notes } ], mermaid, warnings[],
        mock?: [ { entity, label, rows: [ { <field>: <value> } ] } ], html? }
```

`/pb:sync-erd` writes `table[]` + `mermaid` (an `erDiagram` source). The shell is **single-column**: a
**Diagram | Table** toggle, with a relationship-legend popover (crow's-foot 1:1 / 1:N / N:N) on the diagram
and **data-set variant chips** on the table. Per-entity tables share fixed column widths so they line up.
`html` is a legacy pre-baked fallback used only when neither `mermaid` nor `table` is present.

- **`mock`** — optional sample row-sets per entity, surfaced as **per-table data-set variants** in the Table
  view: each entity table that has mock sets gets its own switcher (chips: `Schema` = the field/type/example
  definition, then one per `label`); a table with no mock sets shows no switcher. Selecting a variant swaps
  that table's Example column to the scenario's values (`rows[0]` is representative; an empty set reads as the
  no-data state). Use standard review scenarios — e.g. `New user`, `Empty`, `Returning`. Each set: `label` +
  `rows[]` (objects keyed by field names). Authored by `/pb:sync-erd --mock`.

## The 5 tabs

- **Prototype** — the live **interactive** app driven by the `data-*` runtime (above). Header-line tools (a
  **Browser | App** chrome toggle + an icon-only device switcher over 4 fixed sizes — monitor 1920×1080 /
  laptop 1280×832 / tablet 834×1112 / mobile 390×844, gated by `meta.devices`, default from `meta.device`)
  render the selected screen in a device frame that scales to fit. Browser chrome adds a tab strip +
  back/reload/URL bar; app chrome a titlebar (desktop) or a status bar (tablet/mobile). No screen-switcher.
- **Project Summary** — split: PRD / Insights / Trade-offs (the shared `meta-subtab` sub-tabs) in a scrolling
  left column, with a **scroll-spy table of contents** on the right that tracks the headings in view and
  navigates on click. One viewport, internal scroll.
- **UX Design** — the wireflow from `flow.mermaid` (fills one viewport), with **User stories | Test cases**
  sidebar sub-tabs; hovering a story highlights the flow path it satisfies (above).
- **UI Design** — the DS bar sits on the title line; components split into **Global | Local** sub-tabs (by
  `scope`), each card a single dropdown-driven demo (incl. `state`) + a **Copy code** dialog, plus the
  per-component spec drawer (string-or-structured anatomy/spec) and the Screen view.
- **Data** — single-column **Diagram | Table** toggle over `erd` (above): relationship-legend popover on the
  diagram, data-set variant chips on the aligned tables.

## Render-function inventory

_(Phase 3)_ — ported from v0.4.0: `render`, `renderMetaNav`, `renderMetaPanel`, `renderPrototype`,
`renderMetaSummary` (+ `pbRenderOverview/UserInsights/Tradeoffs/Others`), `renderHandoff`
(+ `pbRenderHandoff*` component/screen/drawer), `renderMetaFlow`/`renderFlowPopulated`,
`renderMetaERD`/`renderERDPopulated`. The per-component `renderCmp*` / per-screen `renderScreen*`
bodies are generated from the registry.

## Sync rules

The **trio** (Prototype + Project Summary + UI Design · component) auto-syncs on `/pb:build`.
Flow, Data, and UI Design · screen are **decoupled** — updated only by `/pb:sync-flow`,
`/pb:sync-erd`, and the screen pass. _(folded from the v0.4.0 hooks: Phase 4–5)_

## Component governance

_(Phase 5)_ — DS-first, Local-first (R0); extend with a variant before spawning (R2); auto-layout
on every Figma frame (R3); kebab-case non-colliding IDs (R4); the naming contract.

## Backlog (gated, not built) — JSX/TSX component export

The prototype artifact is **HTML** (single-file `prototype.html`); `/pb:validate` produces a runnable
reference build of that file, **not** reusable framework components (see the validate command + Stack Lock
note). A real per-component JSX/TSX export from `components[]` is **backlogged**, not in this release.

**Pre-registered success criterion (decide before building it):** a front-end engineer can integrate
**≥ 1 exported component** into a fresh CRA/Vite app and render it correctly in **< 30 minutes**, using only
the generated files + a short README. Build this only if the consumption pilot shows real engineering demand
(D5, Option B). Until then, engineers reuse the **design intent** — tokens, component specs, flows — not files.
