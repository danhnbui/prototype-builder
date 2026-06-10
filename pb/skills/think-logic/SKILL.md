---
name: think-logic
description: Define the behavior of a Product Builder screen or component — states, transitions, validation rules, and conditional rendering. Use when adding interactivity or logic — loaded by /pb:build when logic changes. Maps intent onto the shell's declarative data-* runtime (data-required, data-validate, data-action="submit", data-go, etc.). Not for arranging elements (use think-layout) or connecting whole screens into a journey (use craft-connect-flow).
---

# think-logic

Specify what a screen/component *does*, then express it with the shell's declarative runtime so the
Prototype tab is a real, testable flow — no hand-written event code.

## 1 · States
- Enumerate the states the thing can be in (e.g. `default / loading / error / disabled`).
- **Interactive components MUST declare a `state` property** (`properties[]` entry `id:'state'`, options
  `{label,value}`) — the UI Design tab renders one labeled demo per state.

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

## Output
The state list, the per-input validation, the action/transition map, and any conditional branches — ready
to encode in the `renderSrc` body. Record logic trade-offs (e.g. inline vs on-submit validation) via
`/pb:clarify`.

## Rules
- **A state-less interactive component is a defect** — always declare `state`.
- **Behavior is declarative** — use the data-* runtime; don't hand-author listeners in the body.
