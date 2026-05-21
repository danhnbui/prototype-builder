---
description: Generate or update Tab 1 (Prototype) and Tab 4-Component (Design Handoff component view) from the current spec, plan, and tasks. Runs an inline drift check against the constitution before any trio write. Honors Stack Lock and DS Lock.
handoffs:
  - label: Generate User Flow
    agent: speckit.prototype-builder.sync-flow
    prompt: Generate the user flow diagram for the prototype just built.
  - label: Generate Screen Handoff
    agent: speckit.prototype-builder.handoff
    prompt: Generate Tab 4-Screen handoff for the prototype just built.
---

## User Input

```text
$ARGUMENTS
```

If the user input is empty, build from the latest `.specify/specs/[active]/` artifacts. If user input specifies a story ID or screen name, scope the build accordingly.

## Inline Drift Check *(MUST run before any write to Tab 1, Tab 2, or Tab 4-C)*

This is the **trio drift check** — required because `/build` writes to all three live trio tabs. Custom commands have no SpecKit `before_*` hook, so the check lives here in the command body.

### Step A — Detect: does this build touch the trio?

`/build` always touches Tabs 1 and 4-C and may update Tab 2 (when new trade-offs surface). So **drift check is ALWAYS required for /build.** Skip the trio-touching detector — go straight to step B.

### Step B — Load principles

Read `.specify/memory/constitution.md`. Extract the **Principles** section (numbered list under `## Principles`). Cache the parsed principles for this session — do not re-read on subsequent /build calls in the same session.

If `constitution.md` is missing → HARD FAIL: `"Run /speckit.constitution first."`
If the Principles section is empty → WARN but proceed (no principles = no drift possible).

### Step C — Plan the proposed write

Synthesize a 1-paragraph summary of what `/build` is about to write to Tab 1 and Tab 4-C. Be specific about: components/organisms, layout decisions, state/logic introduced, and any new principles implied.

### Step D — Per-principle contradiction check

For each numbered principle, ask internally:

> "Does the proposed write contradict principle N?"

Collect every contradiction with its principle number and a one-line "because" reason.

### Step E — Branch on result

**If no contradictions** → proceed to "Write Tab 1 + Tab 4-C" below.

**If any contradictions** → output **exactly** this shape, then STOP:

```
⏸ DRIFT DETECTED

Proposed write:
  Tab 1: <summary>
  Tab 4-C: <summary>

Violates principle(s):
  #N — "<principle text>"
     because: <one-line reason>
  #M — "<principle text>"
     because: <one-line reason>

Approve override?  (yes / no / revise)
```

Wait for user prompt + Enter. Do NOT continue. Do NOT interpret silence as approval.

- On `yes` → proceed.
- On `revise` → stop, wait for the next prompt. Treat the next prompt as a fresh `/build` invocation.
- On `no` → stop, no write.

## Stack Lock Check *(G3)*

Read `.specify/memory/constitution.md` Stack Lock section. The chosen language + framework MUST match. If the proposed write deviates:

```
⏸ STACK SWITCH DETECTED

Constitution locks: <language>, <framework>
Proposed write uses: <attempted-language>, <attempted-framework>

Switch stack from X to Y?  (yes / no)
```

Wait for user response. Only proceed on `yes`. On `yes`, also update constitution.md Stack Lock and bump CONSTITUTION_VERSION.

## DS Lock Check *(G2)*

Inspect the proposed write for: inline `style="..."` attributes, external CSS imports, hex colors not in `./design-system/tokens.json`. Any violation:

```
⏸ DS OVERRIDE DETECTED

Locked DS: <source>
Offending styles:
  - <line>: <style>

Extend DS or override this once?  (extend / override / cancel)
```

- `extend` → user updates `./design-system/` to include the needed tokens; re-run build.
- `override` → proceed with the override BUT log it in `.specify/memory/ds-overrides.log`.
- `cancel` → stop, no write.

## Write Tab 1 + Tab 4-C

Once all gates pass:

### Tab 1 (Prototype)
- Source inputs: `spec.md` (user stories, edge cases), `plan.md` (per-story approach), `tasks.md` (implementation order), `./design-system/` (tokens + components).
- Invoke skills: `think-layout` for layout decisions, `think-logic` for state/rules.
- Write only inside the Tab 1 placeholder section of `./prototype/template.html`. Do not touch other tab markers.
- Use only DS tokens for colors, spacing, fonts. Use the locked language + framework.

### Tab 4-Component

Tab 4-Component is the **component library** behind the prototype — a Storybook-grade reference. It must cover **every reusable component the prototype uses** — both standard components (text input, button, alert, etc.) AND any custom organisms from `spec.md`. Do NOT skip standard components: a spec whose components are all standard still needs a populated Component view.

**Write target — `PB_DATA.handoff.organisms`.** A JS array, one object per component, in this exact shape:

```js
{
  id:       'text-input',                 // kebab-case, unique
  name:     'Text input',                 // display name
  renderFn: 'renderCmpTextInput',         // global render function name (see below)
  meta:     'Email + password fields across Sign in, Register…',  // 1-line usage note
  codeLayout: 'stacked',                  // 'stacked' (wide component) | 'side-by-side' (narrow/tall)
  properties: [                           // each property → a <select> on the card
    { id:'state', label:'State', default:'default',
      options:[ { value:'default', label:'Default' }, { value:'error', label:'Error' } ] },
  ],
  code: { lang:'html', snippet:'<label class="field">…</label>' },   // canonical markup
  anatomy: {
    renderProps: { state:'error' },       // FROZEN prop combo → deterministic badge placement
    parts: [
      { n:1, name:'Label', anchor:'.field__label', required:true,
        token:{ name:'--text-secondary', value:'#52525b', kind:'color' } },
    ],
  },
  spec: {
    legend: [ { kind:'dimension', label:'Dimension', color:'#f97316' },
              { kind:'gap', label:'Gap / padding', color:'#2563eb' },
              { kind:'margin', label:'Margin', color:'#db2777' } ],
    renderProps: { state:'error' },       // frozen combo the redline measures
    marginX: 16,                          // declared horizontal margin in px (0 if none)
    stack: [ { anchor:'.field__label', name:'Label' },
             { anchor:'.field__input', name:'Input box' } ],   // top→bottom stacked elements
  },
  uiLogic: [ { target:'Error text', rule:'Show only after blur or submit.' } ],
  usage: {
    demoProps: { state:'default' },       // prop combo for the Usage-tab demo (optional)
    topics: [ { topic:'Label clarity', do:'Use a noun.', dont:'Avoid a full sentence.' } ],
    placement: 'One field per row inside the auth card.',
  },
}
```

`token.kind` ∈ `color | radius | space | size | type` — drives the swatch in the Anatomy table.

**Steps per component:**
1. Identify every reusable component the prototype's screens use (inputs, buttons, alerts, banners, links, custom organisms — invoke `design-component-build` for custom ones).
2. Write a global `renderCmp<Name>(props)` function in `./prototype/template.html` that takes a **props object** (e.g. `{ state:'error' }`) and returns a **live-preview HTML string**. Destructure with defaults: `const { state='default' } = props || {};`. Put a stable `anchor` class name (`.field__label`, `.field__input`, …) on every inner element referenced by an `anatomy.parts` or `spec.stack` entry.
3. Add one entry to `PB_DATA.handoff.organisms` with the full shape above.
4. Wrap the array assignment in a `(function populateHandoffComponents(){ PB_DATA.handoff.organisms = [ … ]; })();` IIFE near the other handoff population code.

**Contract** — the template already ships the consumers; produce data in exactly their shape:
- `pbRenderHandoffComponent()` renders the array as a card list — property `<select>`s + live preview + a code panel (`codeLayout` picks stacked vs side-by-side).
- `pbRenderHandoffDrawer()` renders the click-through 4-tab spec drawer: **Anatomy** (numbered badges + token table), **Specification** (live-measured redline — dimension/gap/margin lines), **UI Logic** (`{target, rule}` rows), **Usage** (demo + `{topic, do, dont}` cards + placement).
- Each drawer tab renders an empty-state line if its key is absent — author every key for a complete card, or omit a key to scaffold it.

Standard DS components used as-is still get a card — record their DS token references in `anatomy.parts[].token` rather than rebuilding the component from scratch.

## Auto-sync Tab 2 (if new content surfaced)

If during build you surfaced a new trade-off or principle, append it to:
- New trade-off → `.specify/specs/[active]/clarify.md` UI Logic Trade-offs section (triggers `after_clarify` hook which writes Tab 2)
- New principle → `.specify/memory/constitution.md` Principles section (triggers `after_constitution` hook)

Do NOT write directly to Tab 2 — let the hook chain do it.

## Confirm to user

```
✅ Tab 1 (Prototype) and Tab 4-Component updated.

Drift check: passed (or: approved override)
Stack lock: honored
DS lock: <honored / N override(s) logged>

Decoupled tabs (3, 4-Screen, 5) may be stale. Run:
  /speckit.prototype-builder.sync-flow   if user flow changed
  /speckit.prototype-builder.handoff     if screens changed
  /speckit.prototype-builder.sync-erd    if data model changed
```

## Important rules

- **NEVER skip the inline drift check.** It is the whole point of /build.
- **NEVER auto-sync Tab 3, Tab 4-Screen, or Tab 5** from /build. Those tabs require their dedicated commands.
- **NEVER write code in Tab 4's Screen view right panel.** That's `/handoff`'s job and even there, code is forbidden.
- **NEVER bypass G2 or G3 by silently coercing styles or mixing stacks.**
- **NEVER invent new SpecKit commands or skill names.**
