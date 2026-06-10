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
**Data only:** render-function bodies are generated from `components[]` / `screens[]`, never stored
here. Design tokens are applied onto `:root` at boot via `applyRegistryTokens`.

### Top-level shape

| Key | Type | Feeds | Notes |
|---|---|---|---|
| `meta.name` | string | — | project name |
| `meta.device` | `'desktop'\|'tablet'\|'mobile'` | Prototype | default device for the preview frame; set at `/pb:init`. Falls back to `'desktop'` |
| `meta.devices` | `('desktop'\|'tablet'\|'mobile')[]` | Prototype | device sizes this project supports — unsupported sizes are disabled in the switcher. Optional; defaults to all three |
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
{ id (kebab, unique), name, renderFn ("renderCmp{PascalCase}"), meta, scope ("global"|"local"),
  level ("atom"|"molecule"|"organism"), codeLayout ("stacked"|"side-by-side"),
  properties[], code{ lang, snippet }, anatomy{ renderProps, parts[] }, spec{ legend, renderProps, marginX, stack[] },
  uiLogic[], usage{ demoProps, topics[], placement } }
```

- **`scope`** — `'global' | 'local'`. Drives the UI Design **Global | Local** sub-tabs. A component reads as
  global when `scope === 'global'` **or** a `dsMatch` exists; otherwise local.
- **`level`** — `'atom' | 'molecule' | 'organism'` — the atomic-design layer. Optional; when present, the UI
  Design Global/Local lists group components by level (atoms → molecules → organisms). Compose upward:
  atoms into molecules, molecules into organisms, organisms onto screens — never inline a one-off (see the
  atomic-composition principle in `constitution.md`).
- **`state` property convention** — if `properties[]` contains a property with `id: 'state'` (each option
  `{ label, value }`), the UI Design demo renders **one labeled variant per state**. **Interactive components
  MUST declare it** (e.g. `default / error / disabled`, `default / loading / disabled`).

Figma fields (`figmaId`, `figmaComponentSetId`, `dsMatch`) are added by `/pb:build-figma-handoff`.
`token.kind ∈ color | radius | space | size | type`.

### `screens[]` (one per screen)

```
{ id (kebab), name, renderFn, layout{ type, gap, maxWidth, padding },
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
flow = { populated, mermaid, stories: [ { title, priority, jtbd, path, scenarios[], node?, status?, preview? } ], html? }
```

`/pb:sync-flow` writes `mermaid` (a `flowchart LR` source) + `stories[]`. The shell renders two sidebar
sub-tabs — **User stories** (title/priority/jtbd/path) and **Test cases** (each `scenarios[]` entry as a
checkbox) — and runs Mermaid with `curve:'basis'` (smooth curved connectors) and classDef colors matching
the on-canvas legend (start/end zinc · decision sky · action lavender · input pink · subprocess purple),
plus a legend popover. `html` is a legacy pre-baked fallback used only when `mermaid` is absent.

### `erd` (Data tab — structured, decoupled)

```
erd = { populated, table: [ { entity, field, type, example, notes } ], mermaid, warnings[], html? }
```

`/pb:sync-erd` writes `table[]` + `mermaid` (an `erDiagram` source). The shell renders a **Diagram | Table**
toggle: Diagram = the `erDiagram`; Table = one styled `<table>` per entity (a real table component, grouped
by `entity`), not text alignment. `html` is a legacy pre-baked fallback used only when neither `mermaid` nor
`table` is present.

## The 5 tabs

- **Prototype** — the live **interactive** app driven by the `data-*` runtime (above); an icon-only device
  switcher (desktop ≤1180px / tablet 834px / mobile 390px, default from `meta.device`) renders the selected
  screen in a device frame — one viewport, internal scroll. No screen-switcher.
- **Project Summary** — PRD / Insights / Trade-offs, navigated by the shared `meta-subtab` sub-tab component.
- **UX Design** — the wireflow from `flow.mermaid`, with **User stories | Test cases** sidebar sub-tabs (above).
- **UI Design** — components split into **Global | Local** sub-tabs (by `scope`), with state-variant demos
  (the `state` property), plus the per-component spec drawer and the Screen view.
- **Data** — the **Diagram | Table** toggle over `erd` (above).

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
