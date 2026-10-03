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
sentence. These are the shapes that recur across real projects (a map editor, a savings app, a
performance-review tool); each comes with an example. The UX Design → Logic tab
draws each as a component; `rules.md` exports it as a table.

- **`cases`** — a condition → outcome table, read top-down (first match wins). Status → label/tone
  maps and empty/error branches are cases too.
  ```json
  { "type": "cases", "rows": [
      { "when": "done", "then": "Completed", "tone": "ok" },
      { "when": "not done + group overdue", "then": "Overdue", "tone": "bad" },
      { "when": "not done + within 48 h of the deadline", "then": "Due soon", "tone": "warn" } ],
    "else": { "then": "In progress", "tone": "info" } }
  ```
  Several inputs → `"inputs": ["role", "cycle"]` and `when` as an object `{ "role": "HR", "cycle": "open" }`.
- **`scope`** — what an action acts on, and what it leaves alone (the half that keeps being forgotten).
  `{ "type": "scope", "acts": ["the polygon being drawn"], "untouched": ["a finished task", "a Reset", "Assign / Unassign zone"] }`
- **`placement`** — what lives on which surface, and what is kept off it.
  `{ "type": "placement", "surfaces": [ { "surface": "Home", "holds": ["Total balance", "You / employer split"] }, { "surface": "Profile", "holds": ["profile"], "never": ["money"] } ] }`
- **`matrix`** — role × action permissions, or control × state enablement.
  `{ "type": "matrix", "rowLabel": "control", "rows": ["Undo", "Finish shape"], "cols": ["0 points", "1", "2+"], "cells": { "Undo": { "0 points": false, "1": true, "2+": true }, "Finish shape": { "0 points": false, "1": false, "2+": true } } }`
- **`validation`** — a refusal, its message and code; name what enforces it.
  `{ "type": "validation", "items": [ { "must": "a split line starts inside the selected polygon", "code": "EDGE_ON_BOUNDARY", "message": "Start the split line inside the selected polygon.", "enforcedBy": "peValidateSplit" } ] }`
- **`formula`** — a computed value, with what each term means and one worked example.
  `{ "type": "formula", "expr": "b = (b + you + employer) × (1 + m)", "terms": [ { "name": "m", "means": "monthly return per scenario" } ], "example": { "inputs": { "m": "0.70902%" }, "result": "2,513,534" } }`
- **`steps`** — a sequence. `{ "type": "steps", "items": [ { "label": "Both figures by source", "detail": "and a consent" }, { "label": "Receiving bank account" }, { "label": "Destructive confirm" } ] }`
- **`params`** — thresholds and limits. `{ "type": "params", "items": [ { "name": "snap radius", "value": 20, "unit": "screen px" } ] }`
- **`effects`** — the store slices it writes and the other screens that change with it.
  `{ "type": "effects", "writes": ["programs"], "ripple": [ { "screen": "Home", "shows": "Deducted from the next payslip" } ] }`
- **`note`** — anything that is genuinely prose. `{ "type": "note", "text": "…" }`

Three more show a **value as itself** instead of describing it. The card puts them under its
**Values** tab, so the rule stays readable above them:

- **`swatches`** — what each state looks like. `value` is the colour; `soft` (a background) draws
  the real status pill; `sample` draws a figure in that colour. Token names fold into a reference.
  `{ "type": "swatches", "items": [ { "label": "Cancelled", "meaning": "cancelled", "token": "color-status-cancel", "value": "#B91C1C", "soft": "#FEE2E2" }, { "label": "Employer share", "meaning": "the employer's contribution", "token": "color-brand-accent", "value": "#FF5200", "sample": "4.000.000 ₫" } ] }`
- **`anatomy`** — an identifier or label broken into its parts, each with its rule. `tone: "warn"`
  marks a part with a caveat.
  `{ "type": "anatomy", "sample": "1050 · Riverside Hub", "parts": [ { "text": "1050", "name": "ops_code", "rule": "Reads first." }, { "text": " · ", "name": "separator", "rule": "Middle dot." }, { "text": "Riverside Hub", "name": "name", "rule": "Supporting text.", "note": "Masked server-side for some hubs.", "tone": "warn" } ] }`
- **`examples`** — an input and exactly what it renders as. `{ "type": "examples", "items": [ { "input": "area 3862.66", "output": "3.862,66 ha" } ] }`

**Title the rule as a statement of what holds** ("A hub reads code first, name second"), never as
a question ("How is a hub identified?") — the question belongs in `decision.question`.

Keep the rule's `summary` to one line: the card's lead is its first sentence. History (who changed it,
what it superseded, the owner's quote, the Figma node, how it was verified) belongs in the decision and
lineage fields — the card's **History** tab draws them as a timeline whose latest entry is the decision.

## Output
The state list, the per-input validation, the action/transition map, and any conditional branches — ready
to encode in the `renderSrc` body. Record a contested logic decision (e.g. inline vs on-submit validation)
as an `ia.rules[]` rule carrying its `decision{}` via
`/pb:clarify`, with its structure in `blocks[]` (§5).

## Rules
- **A state-less interactive component is a defect** — always declare `state`.
- **Behavior is declarative** — use the data-* runtime; don't hand-author listeners in the body.
