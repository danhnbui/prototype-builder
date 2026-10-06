---
name: think-logic
description: Define the behavior of a Product Builder screen or component — states, transitions, validation rules, and conditional rendering. Use when adding interactivity or logic — loaded by /pb:build when logic changes. Maps intent onto the shell's declarative data-* runtime (data-required, data-validate, data-action="submit", data-go, etc.). Not for arranging elements (use think-layout) or connecting whole screens into a journey (use craft-connect-flow).
user-invocable: false
---

# think-logic

Specify what a screen/component *does*, then express it with the shell's declarative runtime so the
Prototype tab is a real, testable flow — no hand-written event code.

## 1 · States
- Enumerate the states the thing can be in (e.g. `default / loading / error / disabled`).
- **Interactive components MUST declare a `state` property** (`properties[]` entry `id:'state'`, options
  `{label,value}`) — the design-system site renders one labeled demo per state (plus a live clickable demo).
  Confirm interactivity with the user before declaring it; a `state`-less interactive component is a defect.

## 2 · Validation (per input)
Express validation with data-attributes on `.field__input` elements:
- `data-required` — must be non-empty.
- `data-validate="email"` — must look like an email.
- `data-minlength="<n>"` — minimum length.
On a failed `data-action="submit"`, the runtime shows an inline error with the `--danger` border.

## 3 · Actions & transitions
Wire behavior with data-attributes (no JS in the body beyond building the string):
- `data-action="submit"` — validate the form, then on success: `data-go="<screen>"` (navigate) ·
  `data-toast="<msg>"` · `data-redirect="<screen>"` + `data-redirect-ms="<n>"`.
- `data-nav="<screen>"` — direct navigation. `data-action="toggle-password"` — reveal/hide a password.

## 4 · Conditional rendering
The render body is plain JS that returns a string — branch on `props.state` to vary markup
(e.g. show a spinner when `props.state === 'loading'`, a danger border when `'error'`).

## 5 · Rule blocks — write the logic as its shape, not as a paragraph
When this logic becomes an `ia.rules[]` entry, give its structure a `blocks[]` entry instead of a
sentence. The UX Design → Logic tab draws **every rule as a stack of visuals**; the rule text, the
decision record, history, open questions and tests sit behind one **Details** drawer. So the blocks
*are* the rule and the decision record is its context. On real projects, over a hundred rules were
written as `kind: "decision"` with prose only and no `blocks[]`: the tab could show text and a log,
nothing to look at. **A rule with a detectable shape is never decision-only.** After writing the rule,
run `python3 "${CLAUDE_PLUGIN_ROOT}/tools/logic_shape.py" registry.json --rule <id> --json`; it lists
the shapes the prose has but the structure lacks. Author them from facts the rule already states —
never invent a value; an unknown stays out of the block, not guessed. `rules.md` exports each block as a table.

Each block below has one line, "use when the prose says…". Fields marked `?` are optional.

### Flow
- **`steps`** — a sequence, drawn as a stepper (guard on the connector, `back` as a dashed return arrow). Use when the prose says "first …, then …", "if it fails, go back to …".
  `{ "type": "steps", "items": [ { "label": "Review order" }, { "label": "Pay", "guard": "cart not empty", "detail": "card or invoice" }, { "label": "Confirm", "back": "Review order" } ], "outcome": { "label": "Order placed" } }`
- **`states`** — what a screen or component looks like in each business state; `interaction` lists the transient ones (hover, focus). Use when the prose says "while loading it shows …, when empty …".
  `{ "type": "states", "component": "order-list", "items": [ { "key": "empty", "label": "No orders", "shows": "illustration + Create button" }, { "key": "error", "label": "Failed", "shows": "retry banner", "tone": "bad" } ], "interaction": ["hover", "focus"] }`
- **`nav`** — a bottom bar or tab set and how screens stack on it. Use when the prose says "tabs are A, B, C; opening X pushes; tapping a tab again resets".
  `{ "type": "nav", "tabs": [ { "key": "home", "label": "Home" }, { "key": "orders", "label": "Orders" } ], "pushed": ["Order detail"], "reset": ["Orders"] }`
- **`branches`** — a show-when tree. Use when the prose says "show X when A, Y when B, otherwise Z" about what is *displayed*.
  `{ "type": "branches", "rows": [ { "when": "invoice overdue", "shows": "red banner", "tone": "bad" } ], "else": { "shows": "nothing" } }`
- **`async`** — what happens while a request is in flight and after. Use when the prose says "pending, then success or failure, partial result …".
  `{ "type": "async", "order": ["tap Save", "request"], "outcomes": [ { "key": "pending", "label": "Saving…" }, { "key": "ok", "label": "Saved", "copy": "Changes saved" }, { "key": "fail", "label": "Not saved", "tone": "bad" } ] }`

### Tables
- **`cases`** — a condition → outcome ladder, read top-down, first match decides. Status → label/tone maps and empty/error branches are cases too. Use when the prose says "if A → X; if B → Y; otherwise Z".
  ```json
  { "type": "cases", "rows": [
      { "when": "done", "then": "Completed", "tone": "ok" },
      { "when": "not done + past due", "then": "Overdue", "tone": "bad" },
      { "when": "not done + due within 48 h", "then": "Due soon", "tone": "warn" } ],
    "else": { "then": "In progress", "tone": "info" } }
  ```
  Several inputs → `"inputs": ["role", "cycle"]` and `when` as an object `{ "role": "Admin", "cycle": "open" }`.
- **`timeline`** — bands along a ruler of dated or ordered marks; `from`/`to` are mark keys, omitted = open-ended. Use when the prose says "before the start …, during …, within 48 h of the end …, after …".
  `{ "type": "timeline", "marks": [ { "key": "start", "label": "Start" }, { "key": "end", "label": "End" } ], "bands": [ { "to": "start", "then": "Not started" }, { "from": "start", "to": "end", "then": "In progress", "tone": "ok" }, { "from": "end", "then": "Closed" } ] }`
- **`matrix`** — role × action permissions, or control × state enablement. `"axis": "role"` puts role dots on rows. Use when the prose says "only Admin can …; Viewer cannot …", "disabled until …".
  `{ "type": "matrix", "axis": "role", "rowLabel": "role", "rows": ["Admin", "Editor", "Viewer"], "cols": ["Edit", "Delete"], "cells": { "Admin": { "Edit": true, "Delete": true }, "Editor": { "Edit": true, "Delete": false }, "Viewer": { "Edit": false, "Delete": false } } }`
- **`order`** — how a list is sorted. Use when the prose says "sorted by A then B, newest first, never by C".
  `{ "type": "order", "keys": [ { "by": "status", "values": ["open", "paid"] }, { "by": "due date", "dir": "asc" } ], "tiebreak": "created date", "never": ["alphabetical"] }`
- **`ladder`** — a fallback chain, try 1, else 2. Use when the prose says "use X, otherwise Y, otherwise Z".
  `{ "type": "ladder", "items": [ { "label": "Nickname" }, { "label": "Full name" }, { "label": "Email" } ], "fallback": "Unnamed" }`
- **`placement`** — what lives on which surface, and what is kept off it. Use when the prose says "Home holds A and B; Profile shows no money".
  `{ "type": "placement", "surfaces": [ { "surface": "Home", "holds": ["Balance", "Recent orders"] }, { "surface": "Profile", "holds": ["Details"], "never": ["Balance"] } ] }`
- **`scope`** — what an action acts on, and what it leaves alone (the half that keeps being forgotten); `unit` names what is scoped. Use when the prose says "applies to X only; Y is untouched".
  `{ "type": "scope", "unit": "one workspace", "acts": ["members of this workspace"], "untouched": ["other workspaces", "archived items"] }`

### Values
- **`validation`** — a refusal, its message and code; `field` draws the input valid and invalid. Name what enforces it. Use when the prose says "must be …, otherwise it shows …".
  `{ "type": "validation", "field": { "label": "Quantity", "sample": "0" }, "items": [ { "must": "at least 1", "code": "QTY_MIN", "message": "Enter 1 or more.", "enforcedBy": "validateQuantity" } ] }`
- **`gate`** — a control that stays disabled until a checklist is met. Use when the prose says "Submit is enabled only when …".
  `{ "type": "gate", "control": "Submit", "requires": ["Title filled", { "label": "At least one item" }], "notGated": [ { "what": "Save draft", "why": "always allowed" } ], "message": "Complete the checklist to submit." }`
- **`formula`** — a computed value, what each term means, one worked example; `split` draws a stacked bar. Use when the prose says "total = …", "X% of …".
  `{ "type": "formula", "expr": "total = subtotal + tax − discount", "terms": [ { "name": "tax", "means": "rate × subtotal" } ], "example": { "inputs": { "subtotal": "100" }, "result": "108" }, "split": [ { "label": "Subtotal", "value": 100 }, { "label": "Tax", "value": 8 } ] }`
- **`params`** — thresholds and limits, each with where it came from (`source`: sourced / assumed / invented — an invented one is flagged). Use when the prose says "within 20 px", "after 30 days", "max 5".
  `{ "type": "params", "items": [ { "name": "snap radius", "value": 20, "unit": "px", "source": "sourced", "ref": "the owner's note" } ] }`
- **`inputs`** — a keymap of keys, gestures and what they do. Use when the prose says "Enter confirms, Esc cancels, Backspace removes the last point".
  `{ "type": "inputs", "rows": [ { "input": "Enter", "when": "drawing", "does": "finish the shape", "never": "submit the form" } ] }`
- **`swatches`** — what each state looks like. `value` is the colour; `soft` draws the real status pill; `sample` draws a figure in that colour. Use when the prose says "paid is green, overdue is red".
  `{ "type": "swatches", "items": [ { "label": "Cancelled", "meaning": "cancelled", "token": "color-status-cancel", "value": "#B91C1C", "soft": "#FEE2E2" } ] }`
- **`anatomy`** — an identifier or label broken into its parts, each with its rule; `tone: "warn"` marks a caveat. Use when the prose says "shown as code · name", "an id is built from …".
  `{ "type": "anatomy", "sample": "1050 · Main Hub", "parts": [ { "text": "1050", "name": "code", "rule": "Reads first." }, { "text": " · ", "name": "separator", "rule": "Middle dot." }, { "text": "Main Hub", "name": "name", "rule": "Supporting text.", "tone": "warn" } ] }`
- **`examples`** — an input and exactly what it renders as. Use when the prose says "3862.66 shows as 3.862,66".
  `{ "type": "examples", "items": [ { "input": "area 3862.66", "output": "3.862,66 ha" } ] }`

### Effects
- **`effects`** — the store slices it writes and the screens that change with it; `toast` previews the message. Use when the prose says "saving updates the dashboard and shows a toast".
  `{ "type": "effects", "writes": ["orders"], "ripple": [ { "screen": "Dashboard", "shows": "Count goes up by one" } ], "toast": "Order saved" }`
- **`edges`** — edge cases, each with what shows, how the user recovers and whether it is covered. Use when the prose says "if offline …, if the list is empty …".
  `{ "type": "edges", "rows": [ { "case": "offline", "shows": "cached list + banner", "recovery": "retry on reconnect", "status": "covered" }, { "case": "two edits at once", "status": "open" } ] }`

### Not in the stack
- **`note`** — anything that is genuinely prose. It goes to the drawer's *Rule text*. `{ "type": "note", "text": "…" }`

The card stacks visuals in a fixed order, whatever the order you wrote them in: the kind-level
lifecycle first, then Flow (`steps` · `nav` · `branches` · `async` · `states`), Tables (`cases` ·
`timeline` · `matrix` · `order` · `ladder` · `placement` · `scope`), Values (`validation` · `gate` ·
`formula` · `params` · `inputs` · `invariants` · `swatches` · `anatomy` · `examples`), then Effects
(`effects` · `edges`).

### Kind-level fields (not blocks)
The rule's `kind` carries its own structure, drawn at the top of the stack. Change `kind` from
`decision` the moment the rule fits one; the decision block stays and keeps rendering.
- **`state-machine`** — `stateField` (the property that holds the state; opts into the reachability check, so a state nothing assigns and not marked `derived` draws dashed), `states[{key, label, condition?, derived?}]`, `transitions[[from, to]]`, `overlays[{key, label, over[], condition?}]` (a condition riding on top of whichever state you are in). Drawn as a statechart; a transition to an earlier state is a "returns to" edge.
  `{ "kind": "state-machine", "stateField": "status", "states": [ { "key": "draft", "label": "Draft" }, { "key": "sent", "label": "Sent" }, { "key": "paid", "label": "Paid" } ], "transitions": [ ["draft", "sent"], ["sent", "paid"] ], "overlays": [ { "key": "overdue", "label": "Overdue", "over": ["sent"], "condition": "past due date" } ] }`
- **`matrix`** — `rows[]` × `cols[]` at the rule level, for a pure table.
- **`constraint`** — `invariants[{must, enforcedBy, when?, message?}]`; one with no `enforcedBy` is a warning.

**Title the rule as a statement of what holds** ("An invoice is paid once its balance is zero"), never
as a question — the question belongs in `decision.question`.

Keep the rule's `summary` to one line: the card's lead is its first sentence. History (who changed it,
what it superseded, the owner's quote, how it was verified) belongs in the decision and lineage
fields; the **Details** drawer draws them as a timeline whose latest entry is the decision. A rule
with no visual says so on its card ("Prose only") and names what its prose looks like.

## Output
The state list, the per-input validation, the action/transition map, and any conditional branches — ready
to encode in the `renderSrc` body. Record a contested logic decision (e.g. inline vs on-submit validation)
as an `ia.rules[]` rule carrying its `decision{}` via
`/pb:clarify`, with its structure in `blocks[]` (§5).

## Rules
- **A state-less interactive component is a defect** — always declare `state`.
- **Behavior is declarative** — use the data-* runtime; don't hand-author listeners in the body.
