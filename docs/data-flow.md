# Data flow — Product Builder v1.3.0

How data moves through Product Builder: the cheap build loop, the Tab-2 sync fold, the decoupled
syncs, and the two exits. See [architecture](architecture.md) for the static picture and the
[router](../CLAUDE.md) for the load-bearing rules.

## The one invariant

```
registry.json  =  state (the model edits this)
prototype.html =  view  (the generator produces this; never hand-edited, never the source of truth)
```

Every flow below reads/writes `registry.json` and only ever produces `prototype.html` through the
deterministic generator (`pb/tools/render.py`).

## The cheap build loop (`/pb:build`)

The loop reads/edits **only the touched slice** and is **trio-gated** — the drift/Stack/DS gate
runs only when a change touches a screen, a component, or logic. It **never** renders
`prototype.html` per tweak; `--render` regenerates it on demand.

```mermaid
flowchart TD
  P["prompt / tweak"] --> R["1 · read the touched slice<br/>token → tokens.&lt;name&gt;<br/>component → components[] by id<br/>screen → screens[] by id<br/>summary copy → meta.*"]
  R --> C{"2 · trio or non-trio?<br/>(screen / component / logic?)"}
  C -- "non-trio<br/>(token value, copy, prop default, size)" --> PATCH
  C -- "trio" --> GATE

  subgraph GATE["3 · gate (trio writes only)"]
    G1["drift — read constitution Principles;<br/>contradiction → ⏸ pause for override"]
    G2["Stack Lock — switch needs approval + decisions.md"]
    G3["DS / component → /pb:build-check-design-system<br/>(reuse → variant → build local)"]
    G1 --> G2 --> G3
  end

  GATE --> PATCH["4 · patch the ONE slice<br/>(changed keys only)<br/>no raw hex / px → tokens"]
  PATCH --> Q{"--render?"}
  Q -- "no" --> STOP["state what changed, STOP<br/>(prototype.html untouched)"]
  Q -- "yes" --> RENDER["5 · render.py registry.json shell.html prototype.html"]
  RENDER --> VIEW["prototype.html refreshed (~0 model tokens)"]
```

Key points:

- **Read the slice, not the file.** The loop never loads the whole registry and never reads
  `prototype.html` to make an edit.
- **Gate-skip is a hard rule.** Never run the full gate ceremony on a non-trio tweak; never skip
  it on a trio write. A drift contradiction pauses with `⏸ DRIFT` and, on override, appends to
  `memory/decisions.md`.
- **The patch is minimal.** Only the changed keys of the one touched slice are written. New
  components/screens append an entry with a kebab-case `id`, a `renderFn`, and a `renderSrc`, plus
  a `render/{components,screens}/<id>.js` body file holding the render code (v1.4 schema 4).
- **Render is batched + deterministic.** Step 5 shells out to the generator; the model never
  hand-emits HTML (the G0.5 spike proved that ~2–3× worse).

### Worked example (from the G3 demo)

| Change | Classified | Gate | Touched | `prototype.html` |
|---|---|---|---|---|
| Tweak a token value | non-trio | skipped | `tokens.<name>.value` | unchanged until `--render` |
| "Add an OTP error state" | trio (logic) | **fires** — reads constitution, principles shape a compliant patch (error text + `--danger` token, no raw hex) | the screen/component slice | unchanged until `--render` |

## The Tab-2 sync fold (no hook)

The v0.4.0 `after_*` hooks + `sync-tab2` are gone. Project Summary (Tab 2) is now written
**directly from the on-ramp command bodies** into `registry.json` — then rendered later via the
normal `--render`.

```mermaid
flowchart LR
  INIT["/pb:init"] -- "meta.overview.objectives + principles[]" --> REG[("registry.json")]
  SPEC["/pb:specify"] -- "meta.overview.objectives (from spec)" --> REG
  CLAR["/pb:clarify"] -- "meta.userInsights + meta.tradeoffs[]" --> REG
  CLAR -- "one entry per trade-off" --> DEC["memory/decisions.md"]
  REG -. "rendered on next /pb:build --render" .-> SUMMARY["Project Summary tab"]
```

- `/pb:init` writes the PRD objective + the constitution Principles as `[{num,title,body}]`.
- `/pb:specify` writes the spec's Objective.
- `/pb:clarify` writes User Insights + UI Logic Trade-offs, and appends one `decisions.md` entry
  per trade-off (`## <date> — <title>` · Decision · Why · Alternatives · Affects).

These bodies write data and **do not render** — the view catches up at the next `--render`.

## The decoupled syncs (UX Design + Data)

Flow (Tab 3) and Data (Tab 5) are **decoupled** — they never auto-fire from `/pb:build` and run no
drift check. Each writes its own slice of the registry, then renders.

```mermaid
flowchart LR
  subgraph flow["/pb:sync-flow (manual)"]
    F1["read memory/spec.md + plan.md"] --> F2["build ONE Mermaid wireflow<br/>+ user-story test checklist"]
    F2 --> F3["write registry.flow<br/>{ populated, mermaid, stories[], wireflowScreens, wireflowNotes }"]
  end
  subgraph erd["/pb:sync-erd (manual)"]
    E1["read spec.md + plan.md;<br/>extract entities"] --> E2["field/type/example table<br/>+ Mermaid erDiagram (5 guardrails)"]
    E2 --> E3["write registry.erd<br/>{ populated, table[], mermaid, warnings[] }"]
  end
  F3 --> RENDER["/pb:build --render"]
  E3 --> RENDER
  RENDER --> VIEW["UX Design / Data tabs refreshed"]
```

- **`/pb:sync-flow`** — one `flowchart LR` (the 18 wireflow rules), wireflow nodes whose labels
  match `registry.screens[].name`, plus a numbered test checklist. Writes `registry.flow`, then
  `--render`.
- **`/pb:sync-erd`** — entities → a field/type/example table + an `erDiagram`, run through the 5
  guardrails (PK, FK, cardinality, PascalCase-singular naming, completeness); warnings become a
  prepended TODO block. Writes `registry.erd`, then `--render`.
- **`/pb:check-drift`** — read-only audit of the trio (screens · components · logic) against the
  constitution Principles. Produces a report only; **never** writes `registry.json` or
  `prototype.html`. (`--save` writes the report to `memory/drift-reports/`.)

## Figma hand-off (`/pb:build-figma-handoff`)

A **one-way** registry → Figma transfer through the Figma MCP, gated G-FP0 → G-FP5 before any
irreversible write. DS-neutral: the match library is `dsMatch.library` from config, never
hardcoded. After a successful push it writes the Figma IDs **back** onto the matching
`components[]` / `screens[]` entries (`figmaId`, `figmaComponentSetId`, `dsMatch`, `figmaFrameId`)
and only those keys — so the next push reconciles instead of duplicating. Roll-forward only.

## The two exits

```mermaid
flowchart TD
  subgraph people["/pb:hand-off --people"]
    PP1["--render"] --> PP2["set config.viewOnly = true<br/>+ config.cover { title, summary, date, by }"]
    PP2 --> PP3["--render again"]
    PP3 --> PP4["prototype.html: authoring CTAs hidden,<br/>cover shown, read-only, opens anywhere"]
  end
  subgraph ctx["/pb:hand-off --context"]
    CX1["export bundle:<br/>registry.json + design-system/ +<br/>memory/constitution.md + memory/decisions.md"]
    CX1 --> CX2["/pb:init --import &lt;bundle&gt; ingests it<br/>into a fresh project"]
  end
  subgraph val["/pb:validate"]
    V1["--render first"] --> V2["scaffold Vite (or --next):<br/>package.json + config + index.html = prototype"]
    V2 --> V3["npm install && npm run build (exit 0)<br/>+ npm run preview"]
  end
```

- **`--people`** renders, flips `config.viewOnly` + writes `config.cover`, and re-renders — the
  shell then hides every authoring CTA across all 5 tabs and shows the cover. Safe to share with
  non-builders.
- **`--context`** exports a portable bundle (registry + DS + the why-log + the locks) that
  `/pb:init --import` ingests to continue the work elsewhere.
- **`/pb:validate`** renders first, scaffolds a runnable Vite/Next build from `prototype.html`, and
  confirms `npm run build` exits 0.

Both hand-off modes and validate **render first** — never hand off or scaffold from a stale view.
