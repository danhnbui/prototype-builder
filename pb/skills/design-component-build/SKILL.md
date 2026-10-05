---
name: design-component-build
description: Build a new local component for Product Builder — its render body file, anatomy/spec, state variants, and token-only styling at the right atomic level. Use when /pb:build decides "build local" (nothing existing fits). Produces the registry entry + the render/components/<id>.js body. Not for deciding reuse-vs-build (that is /pb:build) or screen-level purpose (use ref-blueprint).
user-invocable: false
---

# design-component-build

Construct a new **local** component once `/pb:build` has ruled out reuse and variant.
The output is a registry `components[]` entry plus its render body file.

## 1 · Pick the atomic level
- **atom** — a primitive (button, input, icon).
- **molecule** — a small cluster of atoms (field = label + input + error).
- **organism** — a self-contained section (a sign-in card).
Build the **smallest** level that fits and compose upward — never an organism where a molecule + a variant
would do.

## 2 · Author the entry (data only)
- `id` — kebab-case, unique across global + local (R4).
- `renderFn` — `renderCmp{PascalCase(id)}` (e.g. `text-input` → `renderCmpTextInput`).
- `renderSrc` — `render/components/<id>.js` (create this file with the body).
- `styleSrc` *(optional)* — `render/styles/<id>.css`, only when the component changes across device
  sizes and `meta.responsive` is `true` (§3, *Responsive*).
- `properties[]` — including a **`state`** property if the component is interactive (options `{label,value}`).
  **Prompt-on-interaction:** when the user asks for state / click / hover / any interaction, *confirm the
  component is interactive* and declare `state` (and/or the `data-*` wiring). **Every listed component
  gets a live clickable demo** on the design-system site, whatever it declares; `state` is what puts each
  state in the variant picker and the Variants & spec tab, so a missing `state` leaves an interactive
  component's states impossible to pick or compare.
- `uiLogic[]`, `code`, `usage` — authored into the spec sidecar (`spec/components/<id>.json`, `specSrc`);
  `usage.example` is also the demo the design-system site and `spec_measure.py` render. **`anatomy`,
  `layout`, `elements`, `shape` and `measured` are not authored** — `spec_measure.py` measures them from the
  body (§4) and owns them (schema 13).

**States × variants checklist — fill it before the entry is written.** Every row is either declared or
marked `n/a — <why>` as one `uiLogic[]` line in the sidecar (`n/a hover — static, nothing to point at`):

| Axis | Rows | Declared as |
|---|---|---|
| states | default · hover · focus · active · disabled · loading · error · empty · read-only · each role | an option of the `state` property |
| variant axes | size · kind / intent · tone · with / without icon · density | a `properties[]` entry, `type: "enum"`, with `options[]` |

When the DS reference (`design-system/<name>/<name>.md`) lists this component or its `dsMatch`, the
local variants cover the DS's — name each one missing in the hand-back, never drop it silently.

**Collision priority.** When two states can hold at once (`error` while `loading`, `disabled` and
`selected`), the body's branch order *is* the priority. Write it as the `cases` rows `think-direction`
§4 describes — state · when · what is visible, first match wins — one `uiLogic[]` line per row, and
branch in that order. List overlays (read-only, offline, a save in flight) apart: they sit on top of
any state. A real project shipped three state rows marked "inferred" because no table said which
state wins.

## 3 · Write the body file (`render/components/<id>.js`)
**Bare statements**, not a declaration: `render.py` wraps the file as
`window["renderCmpX"] = function(props){ … }`, so open with `props = props || {};` and end with
`return '…';`. Never write `function renderCmpX(props) { … }` under a comment — the wrap check reads
the first characters, so the named function is declared, never called, and the component renders
`undefined`. Comments say what the body does now; no candidate notes, no dated
layers — history lives in `memory/decisions.md`, cited by number.
- **Tokens only** — every color/space/radius/size is `var(--token)`; no raw hex/px (`lint_registry.py` flags them).
- **Every declared option is branched on** — each `state` and variant value changes what renders (a
  danger border on `'error'`, a spinner on `'loading'`); the default is the fall-through.
- **Every `props.X` the body reads is declared** in `properties[]`. Wiring passed straight through —
  `dataNav`, `dataAction`, `id`, `className`, `full` — is exempt. `R-PROP-USED` and `R-PROP-DECLARED`
  check both halves.
- **A demo for every cell** — `usage.example` in the sidecar is real sample data (the longest label,
  real figures); the site lays it under each enum combination, so every grid cell must render from it.
- **Mark the parts** — `data-part="<name>"` on every meaningful element: the root gets `data-part="root"`,
  then each label, value, icon, slot or inner container a designer would point at (`label`, `amount`,
  `glyph`, `header`). Names are kebab and unique within the body. A child composed with `pbUse('<id>')` needs
  no marker — it is measured as an `instance` part named after its id (`nav-item-1…3` when repeated). The
  part type is inferred (text · glyph · vector · container · slot · instance); `data-part-type="slot"`
  overrides it. A part rendered only under a condition (`props.sub ? … : ''`) becomes **optional**
  automatically — never type "required" or "optional" anywhere.
- Interactive markup uses the data-* runtime (see `think-logic`).
- **Responsive** (`meta.responsive: true`, and the component's shape changes with width — a nav bar,
  a table, a split pane): put `c-<id>` on the root and write the changes in `render/styles/<id>.css`
  with `@container pb-screen (min-width: 600px | 1024px)`, mobile first. Never `@media` (it answers
  the browser window, not the device frame), never a selector outside `.c-<id>`, tokens only, and no
  property that changes left in the inline style. A component that is the same at every width needs
  no sheet. The design-system site renders it in `pb-screen` containers too, so its stage shows the
  wide form and a narrow variant cell the compact one.

## 4 · Verify
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/lint_registry.py" registry.json --strict --exec
```
Read the lines for your id:
- **Static** — kebab + unique id, matching `renderFn`, no raw hex/px, no `R-PROP-DECLARED` (a read
  nobody declared) and no `R-PROP-USED` (an option nothing renders — for `state`, a fake interactive
  state, an ERROR under `--strict`).
- **Executed** — `--exec` runs the body in node once with `{}` and once per `state` option, and fails
  on a throw, a non-string or an empty string. No node → it prints that nothing ran: skipped, not passed.
- **Measured** — `python3 "${CLAUDE_PLUGIN_ROOT}/tools/spec_measure.py" --registry registry.json --component <id> --write`
  writes the anatomy and spec into the sidecar: per part, **padding, margin, item spacing, corner radius and
  colours**. Read it back: every `data-part` is listed, padding / margin / item spacing / radius carry a
  `token` (a raw value means the body used one no token holds), and the parts you expected to be optional
  carry `visibleWhen`. A **card-shaped** root (a fill, a radius and padding, not a native control, ≥ 2 parts)
  gets `shape: "card"`, which is what lists an atom on the design-system site as a Card. The exit code names
  the cause — `/pb:build` §3a has the table: **1** a body threw or a sidecar is not valid JSON (fix it) ·
  **2** Playwright absent (say so in one line and go on) · **3** Chromium missing · **4** a file could not be
  read · **5** the measuring page did not load · **6** `--write` below schema 13 (`/pb:update-version`) ·
  **7** the registry lock is held (wait, run it again).
- **Looked at** — open the design-system site (`/pb:preview` → `/design-system`; or
  `python3 "${CLAUDE_PLUGIN_ROOT}/tools/shot.py" registry.json --path /design-system --full-page`, never a
  hand-written Playwright script) and look at every cell of the variant grid. Two cells that look the same are an option nothing branches on; a cell
  reading "could not render its demo" threw.

## Output
The new `components[]` entry + its `render/components/<id>.js` file (parts marked) + the sidecar (checklist
rows, `cases` priority, `usage.example`, and the measured anatomy/spec), then hand back to `/pb:build` to write the slice.

## Rules
- **Token-only styling** (Principle 2). **Declare `state`** for anything interactive. **Compose upward**,
  don't over-build the level.
- **Declared means rendered** — no option without a branch, no read without a declaration.
- **Run it before you hand it back** — a body that lints clean but returns `undefined` is a failed task.
