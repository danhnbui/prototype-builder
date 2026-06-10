---
description: The cheap build loop. Apply a targeted patch to the touched registry.json slice, trio-gated (drift/Stack/DS gate only when a screen/component/logic changes), and NEVER re-render prototype.html per tweak. Use --render to regenerate the HTML.
---

# /pb:build

The build loop. Reads/edits **only the touched slice of `registry.json`** — never the whole file,
never `prototype.html` by hand. Honors the three token levers from the project router (`CLAUDE.md`).

## Pre-write schema check
Apply the **Schema compatibility** check from `CLAUDE.md` before writing any registry slice. If
`meta.schemaVersion` is below `CURRENT_SCHEMA`, print the banner and suggest `/pb:migrate`. Stop
(do not write) if the current write touches a slice a pending migration changes.

## 0 · Flags
- `--render` — after applying the patch (or on its own), regenerate `prototype.html` from
  `registry.json` via the deterministic generator (step 5). This is the **only** way HTML is produced
  (besides `/pb:hand-off` and `/pb:validate`, which render automatically).
- no flag — apply the registry patch and **stop. Do NOT render.**

## 1 · Read the touched slice (only)
Identify the target and read ONLY that from `registry.json`:
| Prompt targets | Read |
|---|---|
| a token | `tokens.<name>` |
| a component | `components[]` entry by id (+ the DS index first if it's NEW — step 3) |
| a screen / element | `screens[]` entry by id |
| Project Summary copy | `meta.*` |

Do not load the whole registry, and never read `prototype.html` to make an edit.

## 2 · Classify: trio or non-trio
The **trio** = a **screen**, a **component**, or **logic** (states, validation, conditional render).
- **Non-trio** — pure cosmetic: a token value, a copy reword, a prop default, a size/spacing value
  → **skip the gate** (step 3), go straight to the patch (step 4).
- **Trio** — add/restructure a screen, add/change a component, add/change logic → **run the gate**.

> NEVER run the full gate ceremony on a non-trio tweak. NEVER skip it on a trio write.

## 3 · Gate — trio writes only (ported inline drift check + DS-first)
1. **Drift.** Read `memory/constitution.md` → `## Principles`. For each principle, ask: does the
   proposed write contradict it? If any do, **PAUSE**:
   ```
   ⏸ DRIFT
   Proposed  <slice>: <one-line summary>
   Violates  #N — "<principle text>"   because <one-line reason>
   Approve override? (yes / no / revise)
   ```
   On `yes` → append an entry to `memory/decisions.md`, then proceed. On `no/revise` → stop / adjust.
2. **Stack Lock.** Honor `memory/constitution.md` → Stack Lock. A language/framework switch needs
   explicit approval **and** a `decisions.md` entry.
3. **DS / component.** For any new or changed component, run **`/pb:build-check-design-system`**
   (DS-first: reuse → variant → local; naming contract). Invoke skills as needed:
   `think-layout` (layout), `think-logic` (state/rules), `design-component-build` (new custom component).

## 4 · Apply the targeted patch
Edit the **one** touched slice in `registry.json` (changed keys only):
- **token** → set `tokens.<name>.value` (create one tagged `"scope":"local"` if none fits; never a raw hex/px elsewhere).
- **component** → patch the `components[]` entry: a `properties` default, `anatomy`/`spec`, etc. To
  change what it renders, **edit its body file** — `render/components/<id>.js` (pointed at by
  `renderSrc`). The registry holds no render code (v1.4).
- **screen** → patch the `screens[]` entry: add/zorder an element, change `layout`, a `label`, a
  `logicNotes` line. To change what it renders, edit `render/screens/<id>.js`.
- **new component / screen** → append an entry with a **kebab-case** `id`, a `renderFn`
  (`renderCmp{PascalCase}` / `renderScreen{PascalCase}`), and a `renderSrc`
  (`render/components/<id>.js` / `render/screens/<id>.js`); create that `.js` body file with the render
  code. (A legacy inline `render` string still works but is discouraged — `check.py` warns if both are set.)

**Do not touch `prototype.html`. Do not re-render.** State what slice changed and stop (unless `--render`).

### 4a · Interactivity rules (Prototype is a real flow)
The Prototype tab is **interactive** — there is **no screen-switcher**. Wire navigation by emitting `data-*`
attributes in screen/component `render` bodies; the shell's runtime handles them:
- `data-nav="<screen-id>"` — navigate to that screen (links/buttons that move between screens).
- `data-action="toggle-password"` — show/hide the password in its `.field`.
- `data-action="submit"` — validate the enclosing form's `.field__input`s, then on success:
  `data-go="<screen-id>"` (navigate) · `data-toast="<msg>"` (toast) ·
  `data-redirect="<screen-id>"` + `data-redirect-ms="<n>"` (auto-navigate after a delay).
- input validation: `data-required` · `data-validate="email"` · `data-minlength="<n>"`.

Two more rules:
- **Interactive components MUST declare a `state` property** (`properties[]` entry `id:'state'`, options
  `{label,value}`) — e.g. `default / error / disabled`, `default / loading / disabled`. The UI Design demo
  renders one labeled variant per state. A `state`-less interactive component is a defect.
- **`meta.device`** (`'desktop'|'tablet'|'mobile'`) sets the Prototype's default device frame. It's seeded at
  `/pb:init`; change it here only if the prototype's target form factor changes.

## 4.5 · Validate the contract (advisory, after every patch)
Run the contract validator on the patched registry — **read-only, no render** (so the
token levers NS2/NS3 stay intact). From the project root:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/check.py" registry.json
```
Surface any `ERROR`/`WARN` lines to the user as advice (kebab/renderFn/orgId/token-kind
issues, a `</script>` page-killer, raw hex/px, a missing `danger` token). This is
**advisory** in the loop — it never blocks a build tweak — but the same check runs
`--strict` and **fail-closed** at `/pb:hand-off` and `/pb:validate` before any render,
so fixing findings now avoids a blocked exit later.

## 5 · Render — batched, deterministic, on demand only
Rendering is the deterministic generator — **never** hand-write HTML (the G0.5 spike proved that is
~2–3× worse). From the project root:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/render.py" registry.json \
        "${CLAUDE_PLUGIN_ROOT}/template/prototype.html" prototype.html
```
(In-place dev tree: generator `tools/render.py`, shell `template/prototype.html`.)

## Crown-jewel rule
The render machinery (`pbRender*`, the 4-tab spec drawer, wireflow, ERD) is ported as-is and reads from
`PB_DATA`, which the shell's adapter rebuilds from `registry.json` each load. You produce **DATA**;
the generator + adapter produce the view.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
