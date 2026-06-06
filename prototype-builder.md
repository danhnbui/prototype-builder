# Product Builder — playbook

The detailed reference behind the [router](CLAUDE.md). Read the router first. This file
documents the `registry.json` data contract, the render-function inventory, the sync rules,
and component governance. (Sections marked _(Phase N)_ are filled as those phases land.)

## registry.json — the data contract

`registry.json` is the **single source of truth** the build loop edits. `prototype.html` is a
rendered **view**: at `/pb:build --render` the generator inlines `registry.json` into the HTML's
`PB_REGISTRY`, and a thin adapter (`adaptRegistryToPBData`) maps it onto the in-memory `PB_DATA`
shape the render machinery already reads — so the ported v0.4.0 render functions are unchanged.
**Data only:** render-function bodies are generated from `components[]` / `screens[]`, never stored
here. Design tokens are applied onto `:root` at boot via `applyRegistryTokens`.

### Top-level shape

| Key | Type | Feeds | Notes |
|---|---|---|---|
| `meta.name` | string | — | project name |
| `meta.overview` | `{ objectives, principles[] }` | Project Summary | from spec + constitution |
| `meta.userInsights` | `{ quantitative, researchSummary, executiveSummary }` | Project Summary | from `/pb:clarify` |
| `meta.tradeoffs[]` | `[{ title, question, options, decision, why, tabsAffected }]` | Project Summary | UI Logic Trade-offs |
| `meta.others` | string \| null | Project Summary | freeform |
| `tokens{}` | `{ "<name>": { value, kind } }` | all (CSS vars) | injected onto `:root`; `kind ∈ color\|radius\|space\|size\|type\|shadow\|alias` |
| `components[]` | organism objects | UI Design · component | the component library — shape below |
| `screens[]` | screen objects | Prototype + UI Design · screen | shape below |
| `staleness{}` | per-tab `{ lastSyncedPromptCount, currentPromptCount }` | flow / handoff / erd badges | |
| `flow.populated` / `erd.populated` | bool | Flow / Data | decoupled-tab flags |

### `components[]` (one per reusable component)

Ported **verbatim** from the v0.4.0 `PB_DATA.handoff.organisms` shape:

```
{ id (kebab, unique), name, renderFn ("renderCmp{PascalCase}"), meta, codeLayout ("stacked"|"side-by-side"),
  properties[], code{ lang, snippet }, anatomy{ renderProps, parts[] }, spec{ legend, renderProps, marginX, stack[] },
  uiLogic[], usage{ demoProps, topics[], placement } }
```

Figma fields (`figmaId`, `figmaComponentSetId`, `dsMatch`) are added by `/pb:build-figma-handoff`.
`token.kind ∈ color | radius | space | size | type`.

### `screens[]` (one per screen)

```
{ id (kebab), name, renderFn, layout{ type, gap, maxWidth, padding },
  elements[ { id, label, orgId, tokens[], sizing, state, uiLogic, bounds? } ], logicNotes[], figmaFrameId? }
```

### Runtime-only — **NOT persisted to registry.json**

`handoff.view`, `handoff.selectedScreenId`, `handoff.selectedElementId` are ephemeral UI state,
rebuilt fresh from the registry on each load and never written back. (This is why a click in the
prototype never dirties `registry.json`.)

## The 5 tabs

Prototype · Project Summary (PRD / Insights / Trade-offs) · UX Design (Flow / Tests) ·
UI Design (DS / Local / Screen) · Data (field / type / example table, then ERD). _(restructure: Phase 5)_

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
