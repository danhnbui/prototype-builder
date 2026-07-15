---
name: sandbox-test
description: Drive the Product Builder Prototype sandbox to verify authored scenario tests — encode the test{} step/expect vocabulary, resolve targets against the live #proto-frame, run per-role and security passes, and write each scenario's lastResult. Use when running /pb:test so a scenario becomes a real, observed pass/fail. Not for authoring the scenarios (that is /pb:sync-flow's QA pass) or building screens (use /pb:build).
---

# sandbox-test

Turn an authored scenario into an **observed** result. A story scenario may carry a `test{}` block; this
skill defines exactly how to execute it against the shell's live Prototype sandbox and record the outcome —
never by reading the design, always by driving it.

## The `test{}` vocabulary (the contract)
A scenario in `flow.stories[].scenarios[]` is either a string or an object `{text, category}`. A test-bearing
scenario adds:
```
test: { start: "<screenId>", steps: [ {do, target, value?} ], expect: [ <one-of below> ] }
```
- **start** — set `state.protoScreenId = start` before the first step (the sandbox begins on that screen).
- **steps[].do** ∈ `fill` · `click` · `nav` · `submit` · `toggle-password` · `back`:
  - `fill` — `target` = field label · CSS selector · a `data-*` value; `value` = the string to type.
  - `click` / `nav` / `submit` / `toggle-password` — `target` = a CSS selector or a `data-*` value.
  - `back` — no target (invoke the sandbox's history back).
- **expect[]** — each item is **exactly one** of:
  - `{"screen":"<id>"}` → `state.protoScreenId === id`.
  - `{"text":"..."}` → `document.querySelector('#proto-frame').textContent` contains it.
  - `{"errors":{"min":N}}` / `{"errors":{"count":N}}` → visible `#proto-frame .field__error` count `>= N` / `=== N`.
  - `{"toast":"..."}` → a `.proto-toast` with that text appeared during the scenario.
  - `{"no-console-error": true}` → no `console.error` / `pageerror` fired during the scenario.

## Target resolution (in order)
Resolve a `target` against the current `#proto-frame`; first match wins. The order differs by verb:
- **`fill`** — 1. **Field label** (the `.field__input` whose label / placeholder / `aria-label` matches — the author-friendly default) · 2. **CSS selector** · 3. **`data-*` value**.
- **`click` / `nav` / `submit` / `toggle-password`** — 1. **CSS selector** (`.btn`, `#email`, `[data-nav="dashboard"]`) · 2. **`data-*` value** (any `data-*` attribute equal to the string, e.g. `submit` → `[data-action="submit"]`, `dashboard` → `[data-nav="dashboard"]`).
If nothing resolves, the step **fails** with a clear "target not found" detail — never silently no-op.

## Run discipline
- **Server.** Reuse the single running `/pb:preview` server (`--server`) whenever one is up — never boot a
  second (one preview per project). Otherwise run one isolated headless instance for the run.
- **Reset between scenarios.** Call `pbResetSandbox()` before each scenario so state (screen, field values,
  toasts, history) never leaks between tests. Then set `state.protoScreenId = test.start`.
- **Roles (`--roles`).** Run each scenario once per `meta.roles`: `setProtoRole(id)`, then assert role-gated
  screens (`screens[].roles`) and elements (`data-roles`) are visible only to permitted roles — a role with
  `isAdmin:true` bypasses all gating. A screen the active role can't see must not be reachable.
- **Security (`--security`).** A static scan of the registry + render bodies (secrets, `</script>`
  page-killers, unescaped injection, external network calls) — a finding is an error, not a warning.

## Recording the result
Write each scenario's `lastResult { status, detail, ranAt }`:
- `status` ∈ `pass` (every expect held) · `fail` (any expect missed, or a step errored) · `untested`
  (not run this pass).
- `detail` — one line: the first failing expect, or "N steps, M expects — all held".
- `ranAt` — ISO-8601 Z timestamp of the run.
The UX-tab glyph reads `lastResult.status`: `pass → ✓`, `fail → ✗`, `untested/absent → ○`; a scenario with
**no** `test{}` stays `☐` (manual). This is the **only** registry slice a test run writes.

## Rules
- **Observe, don't shape** — never edit a screen / component / logic to make a scenario pass.
- **Fail-closed** — an unresolved target, a step error, or a security finding is a **failure**, never a skip.
- **Untested ≠ pass** — a scenario that didn't run is `○ untested`, never reported green.
- **Write only `lastResult`** — the design slices are read-only to a test run.

## `--roles` threat model (what the audit does and does not guarantee)
`--roles` is a best-effort *visibility* audit: for each role it navigates every screen and flags any `data-roles`
element (or its rendered content) that is effectively visible to a role not in its set — measured by the element's
box, its element descendants' boxes, and its rendered text (a `Range`), so `display:contents`, `visibility:hidden`
parents with visible children, and opacity tricks are all caught. It **assumes role-agnostic render bodies** (the DS
contract: bodies emit the same markup for every role and gating is declarative via `data-roles` + the shell). A body
that *deliberately branches on `state.activeRole`* to paint content for a user while hiding it from this single-pass
audit is **out of scope** — `/pb:build` never emits such bodies, and no static audit can defeat an adversarial one.
