---
description: Generate or update Tab 3 (User Flow). Produces a Mermaid `flowchart` diagram following the 18 enforced rules of the user-flow guide + a numbered list of user stories that act as the test checklist. Tab 3 is decoupled — never auto-triggers.
---

## User Input

```text
$ARGUMENTS
```

If user input names a specific story or flow, scope to that. Otherwise, generate the full flow across all P1/P2/P3 user stories in spec.md.

## Execution flow

### Step 1 — Read inputs
- `.specify/specs/[active]/spec.md` → user stories, JTBDs, acceptance scenarios
- `.specify/specs/[active]/plan.md` → per-story approach, state transitions

### Step 2 — Read the user-flow guide (required)
The full set of rules + shape standard + validation checklist lives in [`docs/USER-FLOW-GUIDE.md`](../../docs/USER-FLOW-GUIDE.md) — load it. **Every output MUST conform.** Violating a rule is a defect, not a stylistic choice.

**Platform rules (v0.3.10+, §0 of the guide) — non-negotiable:**
- **3:7 canvas layout** — test checklist on the LEFT (3 cols), flowchart canvas on the RIGHT (7 cols)
- **Legend with `?` popover** — pill-shaped legend in the top-right of the canvas, click opens a popover explaining every shape
- **Full-width container** — flow-doc grid spans the entire Tab 3 panel width
- **One combined flow by default** — express the WHOLE prototype as a single Mermaid flowchart that covers every user story (including edge cases). Push per-story detail into `[[Subprocess]]` nodes; the test checklist on the left maps each story to a path through the combined flow. Only stack multiple `<div class="flow-doc-section">` sections inside `#flow-stage` when flows are truly independent (different actors AND different goals) OR when a single combined flow exceeds 9 nodes even after subprocess extraction. **ASK the user** when unsure. The `.flow-canvas` / `.flow-viewport` / `.flow-stage` trio still gives pan + zoom + fit-to-view for any flow count
- **`LR` direction always** — Start on the left, End(s) on the right
- **Color-coded shapes** via `classDef` (zinc-900 / lavender / sky / pink / purple — see guide §0.6 for the v0.3.9 palette)
- **Orthogonal connectors (horizontal/vertical only)** — init Mermaid with `flowchart: { curve: 'step', useMaxWidth: false }`

**Craft constraints (the 18 rules, §3 of the guide):**
- Use ONLY the 6 standard shapes: stadium `([…])`, rectangle `[…]`, diamond `{…?}`, parallelogram `[/…/]`, subprocess `[[…]]`, cylinder `[(…)]`
- Single `Start` + at least one `End`. No dead-end branches (loops back to existing nodes are OK)
- Decision labels end with `?`. Every branch labeled `-- Yes -->` / `-- No -->`
- Sentence case in all labels. Verbs in actions. Questions in decisions
- 7±2 rule: 5-9 nodes per flow. Excess → extract `[[Subprocess]]`, then ASK if still over
- No emojis, no HTML, no Title Case, no ALL CAPS in labels

### Step 3 — Invoke supporting skills
- `craft-connect-flow` skill (from `./.claude/skills/craft-connect-flow/SKILL.md`) — for screen-to-screen navigation patterns, shared state, entry/exit points, deep links
- `design-generate-userflow` skill (if present in `./.claude/skills/`) — the canonical source of the 18 rules; identical to the in-repo guide

### Step 4 — Generate the Mermaid flowchart

Produce ONE Mermaid block that covers the whole prototype (combined flow). Push per-story detail into `[[Subprocess]]` nodes; the test checklist on the left side of the canvas maps each story to a path. Only emit multiple Mermaid blocks if the combined flow can't fit in 9 nodes after subprocess extraction (and ask the user first).

Each block uses the standard v0.3.10+ output format with the color-coded `classDef` palette below:

````markdown
**Flow N — <title>**
**Actor:** [actor] · **Goal:** [goal]

```mermaid
flowchart LR
  Start([Entry point]):::cStart --> A[First action]:::cAction
  A --> D{Decision question?}:::cDecision
  D -- Yes --> B[/User input/]:::cInput
  D -- No --> C(Subprocess):::cSubprocess
  B --> End([Success state]):::cEnd
  C --> End

  classDef cStart       fill:#0f172a,stroke:#000000,color:#ffffff,stroke-width:1.5px
  classDef cEnd         fill:#0f172a,stroke:#000000,color:#ffffff,stroke-width:1.5px
  classDef cDecision    fill:#DBEAFE,stroke:#60A5FA,color:#1e3a8a,stroke-width:1.5px
  classDef cAction      fill:#F3E8FF,stroke:#C084FC,color:#581c87,stroke-width:1.5px
  classDef cInput       fill:#FCE7F3,stroke:#EC4899,color:#831843,stroke-width:1.5px
  classDef cSubprocess  fill:#EDE9FE,stroke:#7C3AED,color:#4c1d95,stroke-width:2px
```

**Important**: use `C(Subprocess)` (rounded-rect syntax), NOT `C[[Subprocess]]` — only the rect form accepts the 24px corner radius from the post-render step in §7.
````

Each flow goes into its own `<div class="flow-doc-section">` block (heading + actor/goal sub + Mermaid). All sections live inside `#flow-stage` so the user pans + zooms over every flow at once.

The host template must initialize Mermaid with `{ flowchart: { curve: 'step', useMaxWidth: false } }` and then measure + size the stage so `initCanvas('flow', W, H)` wires up pan/zoom. See `assets/template.html`'s `renderMetaFlow()` for the reference init pattern.

For multi-actor flows, use `subgraph` swimlanes (max 3 lanes; if more, decompose into separate flows).

### Step 5 — Validate against the 18 rules

Run the validation checklist from `USER-FLOW-GUIDE.md` §7. Each violation is a defect — fix before delivering. Examples:
- Exactly one `Start` node?
- All paths terminate at an `End` node?
- Every decision label ends with `?`?
- Every branch has `-- label -->`?
- Node count 5–9 (or subprocess for excess)?
- No Title Case / ALL CAPS in labels?
- Mermaid syntax valid (no unclosed brackets, no undefined nodes)?

### Step 6 — Generate the user-stories checklist
Below the Mermaid block, render a numbered list of one user story per flow path:

```markdown
1. **<Story title> (P1)** — <JTBD> [Story 1 in spec.md]
   - Path: <entry> → <action> → <action> → <outcome>
   - Test checklist:
     - [ ] <acceptance scenario 1>
     - [ ] <acceptance scenario 2>

2. **<Story title> (P2)** — <JTBD>
   ...
```

The checklist doubles as the **future testing checklist** (per Tab 3 guardrail #2 in [`03-data-flow.md`](../../docs/03-data-flow.md) §3.1).

### Step 7 — Write to Tab 3 of `template.html`

The Tab 3 layout is the v0.3.10+ **3:7 grid with a zoomable canvas**: test checklist on the LEFT, combined-flow canvas on the RIGHT. Update all four pieces:

1. **Set `PB_DATA.flow.populated = true`** to flip Tab 3 from empty state to populated view.
2. **Replace the body of `renderFlowPopulated()`** with the new `.flow-doc-grid` structure containing:
   - `<aside class="flow-doc-side">` — wrapping the test checklist (`.flow-doc-stories > li` per user story, with `.flow-doc-story-title` / `.flow-doc-story-path` / `.flow-doc-story-check`)
   - `<section class="flow-doc-main">` — header with title + actor/entry/goal sub + the legend pill button (`onclick="openLegendPopover(this)"`), then `<div class="flow-canvas" id="flow-canvas">` containing `<div class="flow-viewport" id="flow-viewport"><div class="flow-stage" id="flow-stage">…</div></div>` plus the `flow-zoom-controls` (+ / − / ⊙), `flow-zoom-readout`, and `flow-hint`. Inside `#flow-stage`, place **one `<div class="flow-doc-section">`** with the combined flow (heading + intent + `<div class="mermaid">…</div>`). Only add more sections when truly necessary per platform rule §0.4. Below the canvas: summary + validation paragraphs
3. **Initialize Mermaid + canvas** in `renderMetaFlow()`:
   ```js
   mermaid.initialize({
     startOnLoad: false,
     theme: 'base',
     flowchart: { curve: 'step', htmlLabels: true, padding: 18, useMaxWidth: false, nodeSpacing: 50, rankSpacing: 60 },
   });
   mermaid.run({ querySelector: '#flow-stage .mermaid' }).then(function () {
     var stage = document.getElementById('flow-stage');
     stage.classList.add('flow-stage-flow');
     Array.from(stage.querySelectorAll('svg')).forEach(function(svg){
       svg.style.maxWidth = 'none';
       svg.removeAttribute('width');
       svg.removeAttribute('height');
     });
     // v0.3.12 — apply 24px corners to Action + Subprocess rectangles
     stage.querySelectorAll('.node.cAction > rect, .node.cSubprocess > rect').forEach(function(rect){
       rect.setAttribute('rx', '24'); rect.setAttribute('ry', '24');
     });
     stage.style.width = 'auto'; stage.style.height = 'auto';
     stage.style.marginLeft = '0'; stage.style.marginTop = '0';
     requestAnimationFrame(function () {
       requestAnimationFrame(function () {
         var bbox = stage.getBoundingClientRect();
         var W = Math.max(1024, Math.ceil(bbox.width));
         var H = Math.max(720,  Math.ceil(bbox.height));
         stage.style.width = W + 'px'; stage.style.height = H + 'px';
         stage.style.marginLeft = -(W/2) + 'px'; stage.style.marginTop = -(H/2) + 'px';
         initCanvas('flow', W, H);
       });
     });
   });
   ```
4. **Preserve all other tabs.** Tab 1 / 2 / 4 / 5 must remain untouched.

If `openLegendPopover` or `.flow-stage-flow` isn't yet defined in the template (pre-v0.3.9 install), inline the helper next to `recopyFromPopover` and add the CSS modifier next to `.flow-stage-erd`. See `assets/template.html` in the extension repo for the reference implementation.

## Confirm to user

```
✅ Tab 3 (User Flow) updated.
   Flow: N nodes, M edges (Mermaid `flowchart TD`)
   User stories: K stories (P1: a, P2: b, P3: c)
   Test checklist items: T
   Rules validation: all 18 passed

Drift check: skipped (Tab 3 is decoupled by design)
```

## Important rules

- **NEVER violate any of the 18 enforced rules** in [`USER-FLOW-GUIDE.md`](../../docs/USER-FLOW-GUIDE.md). Each violation is a defect to fix before delivery, not a stylistic option.
- **NEVER run drift check from /sync-flow** — Tab 3 is decoupled and trio principles don't constrain user-flow representation.
- **NEVER auto-trigger this from /build** or any other command. Only the user invokes /sync-flow.
- **NEVER omit the user-stories checklist** below the diagram — the checklist is what makes Tab 3 testable.
- **NEVER use external font files** in the diagram — Mermaid uses the page's font stack by default.
- **NEVER use emojis, HTML, Title Case, or ALL CAPS** in node labels.
- **NEVER mix flow directions** — pick TD or LR per flow and stick to it.
