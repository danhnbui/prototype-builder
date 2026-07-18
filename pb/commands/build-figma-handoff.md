---
description: Sub-command of /pb:build. One-way registry → Figma transfer via the Figma MCP, with a 5-gate clarify pass (G-FP0–G-FP5) before any irreversible Figma write, then a mandatory render audit (G-FP6) that blocks completion until the pushed result verifies. DS-neutral (the matched library is read from config, never hardcoded). Auto-layout on every created frame (R3). v1 is one-way only; bi-directional sync is out of scope.
---

# /pb:build-figma-handoff

Push the prototype's components and screens to a Figma file. Reads from **`registry.json`**
(`components[]` / `screens[]`) — the same data the prototype renders from. **DS-neutral:** the design
system to match against is read from `memory/constitution.md` → Design System Lock and mirrored in
`figma-transfer.json` as `dsMatch.library` — there is no hardcoded library name anywhere.

> **Mandatory path — this is the ONLY sanctioned way to put prototype content into Figma.**
> NEVER hand-draw or hand-emit frames into Figma outside this command — that yields untokenized,
> untracked, non-reusable pixels (the anti-pattern). Run every gate in order; the push is
> **done only when Gate G-FP6 (render audit) passes**. A failing audit blocks Step 7 and the
> hand-off is reported incomplete — never silently accepted.

## User input
```text
$ARGUMENTS
```
| Flag | Default | Effect |
|---|---|---|
| `--scope=components\|screens\|both` | ask in G-FP0 | What to push |
| `--screen=<id>` | all in scope | Restrict screens push to one screen |
| `--organism=<id>` | all in scope | Restrict components push to one component |
| `--batch` | refuse if >1 screen or >5 components | Allow large pushes |
| `--dry-run` | false | Run all gates + show the plan, skip the actual Figma writes |
| `--force` | false | Skip the no-op hash check (G-FP1.5) |
| `--rematch` | false | Re-prompt DS matches even for already-bound components |

## Gate G-FP0 — Scope selection
If `--scope` is absent, ask:
```
What's the push scope?
  1) components — push the component library to Figma
  2) screens    — push screen frames using existing components
  3) both       — components first, then screens consume them as instances
Choose 1-3:
```
Wait for prompt + Enter. Save to `figma-transfer.json.lastScope`.

## Gate G-FP1 — Pre-flight integrity (always runs)
Sequential. ANY failure → HARD FAIL with the exact message; no Figma writes yet.
1. **Figma MCP reachable** — call Figma `whoami`. On error → HARD FAIL with: `Figma MCP not reachable. Configure the Figma connector and re-run.`
2. **Registry loaded** — read `registry.json`; confirm it parses and has `components[]` / `screens[]`. If empty → HARD FAIL: `registry.json has no components/screens. Run /pb:build first.`
3. **`figma-transfer.json` exists OR seed it** — if absent, prompt for the Figma file URL (`https://www.figma.com/{file|design}/<key>/...`), extract `<key>` as `fileKey`, and write `figma-transfer.json` from `figma-transfer.template.json`. Set `dsMatch.library` to the Design System Lock name from `memory/constitution.md`.
4. **Target page + root frame** — if `target.pageId` is null: `Figma:get_metadata`, list pages, ask which page; then create/pick a root frame. Persist `pageId/pageName/rootFrameId/rootFrameName`.
5. **No-op detection** — SHA-256 the in-scope slice of `registry.json` (`components` / `screens` / both). If it equals `figma-transfer.json.lastPushedHash[<scope>]` and `--force` is absent → STOP (`✓ No changes since last push.`).

## Gate G-FP2 — Identity audit (per scope)
- **components / both:** each component with a `figmaComponentSetId` in `figma-transfer.json` → `update`; else `new`.
- **screens / both:** each screen with a `figmaFrameId` → `update`; else `new`.
- **Variant-axis change (components):** compare `properties[]` to `figma-transfer.json.propertyMapping`. A new property or new option values → flag `axis-change`. **NEVER auto-add a variant axis** — it surfaces as its own group here.
- **Affected-screen analysis (components):** for every `update` / `axis-change` component, list the **screens that reference it** (`screens[].elements[].orgId === <component id>`). Re-pushing the component re-renders its instances on those frames — name them so the blast radius is explicit before confirming. (This mirrors the "⚠ affects N screens" line shown in the UI Design push panel.)

Output the audit (new / updated / axis-change counts + ids + total writes estimate + **affected screens per updated component**) and ask `Proceed to G-FP3? (yes / cancel)`. On `cancel` → stop.

**Batch guard:** if (new+updated screens) > 1 OR (new+updated components) > 5 and `--batch` is absent → HARD FAIL (re-run with `--batch` or scope down).

## Gate G-FP3 — Token resolution (always runs)
Collect every token reference in scope — the **union** of component `anatomy.parts[].token.name` + `spec.stack[]`, screen `elements[].tokens[]`, **and every `var(--name)` used in the in-scope render body files** (each entry's `renderSrc` →
`render/components/<id>.js` / `render/screens/<id>.js`; resolve and scan it, falling back to a legacy
inline `render` string if present) (so a token that is used but not separately declared — e.g. spacing — is never silently skipped). Load `figma-tokens.json`. For each unique token: use the existing mapping, or propose one via `Figma:search_design_system` (query built from the token name). Pause:
```
⏸ TOKEN MAPPING NEEDED
  --brand           → {DS}/Colors/brand              (VariableID:…)  [match by name]
  --text-secondary  → {DS}/Colors/text/secondary     (VariableID:…)  [match by name]
  --custom-orange   → NO MATCH FOUND                                 [will create local]
Accept all proposed?  (yes / edit / cancel)
```
`{DS}` is the configured library name. On `yes` → save to `figma-tokens.json`. NO-MATCH tokens default to a local variable in a `Prototype tokens` collection (persisted; never coerced to a raw hex/px).

## Gate G-FP4 — DS component match (components or both only)
Skip if scope is `screens`. For each `new` component: if `dsMatch.figmaComponentId` is set and `--rematch` absent → reuse it (instance-swap); else propose via `Figma:search_design_system` on the component `name`. Pause:
```
⏸ DS COMPONENT MATCH   (library: {DS})
  text-input     → {DS}/Forms/Text input    (…)
  primary-button → {DS}/Buttons/Primary     (…)
  alert-banner   → NO MATCH FOUND                       [will create local]
Accept all?  (yes / edit / cancel)
```
On `yes` → save to `figma-transfer.json.components[<id>].dsMatch`. NO-MATCH → **create local** under the root frame (not into the library); persisted so future pushes update in place.

## Gate G-FP5 — Push plan + confirmation (irreversible)
**The ONLY gate for the irreversible write.** Output the full plan: scope · target · page · root · components (create-local / update / instance-swap to `{DS}`) · screens (create / update) · tokens (bind / create-local) · the auto-layout policy. Then ask `Proceed? (yes / no / show-detail)`.

**Auto-layout (R3):** **every created frame uses auto-layout — no absolutely positioned children.** Sizing axis defaults to hug-V / fill-H; frames with explicit `sizing.width`/`sizing.height` use those. A child whose layout can't be expressed as auto-layout is a HARD FAIL, not an absolute-position fallback.

If `--dry-run` → print the plan and STOP (no writes, no contract updates).

## Step 6 — Execute (only after G-FP5 `yes`)
Ordered, each a `Figma:use_figma` call (load the `figma-use` skill first):
1. **Tokens** — create each local token in the chosen collection; record VariableIDs.
2. **Components** (skip if scope=screens) — build each `create-local` from `anatomy.parts[]` + `spec.stack[]` + `properties[]` **with auto-layout**; apply diffs for `update`; record `componentSetId`/`componentId`. DS-matched components: no write, just record the binding. **Any `anatomy.parts[]` entry with an `orgId` is a NESTED GLOBAL — do NOT redraw it as a local frame: `createInstance` of that global's `dsMatch.componentKey` (`importComponentSetByKeyAsync` → pick the variant → `createInstance`), place it in the parent's auto-layout, and apply the part's text override. Record each under `figma-transfer.components[<parent>].nestedInstances[<orgId>]` (`{instanceId, componentKey, dsName}`). Do this per variant of the parent ComponentSet.**
3. **Screens** (skip if scope=components) — create a frame in `rootFrameId` per screen; for each element create a child node **with auto-layout** per the sizing heuristic; DS-matched element components inserted as **instances**, not local copies; record `frameId` + element map.
4. **Token bindings** — bind each element's computed property to its VariableID.
5. **Instance bindings** — ensure each instance points at the correct `{DS}` library component.

**Progress reporting:** as each component / screen completes, print a one-line tick (`✓ pushed <name> (3/7)`). If the live `/pb:preview` server is up, also drive the in-app progress widget by evaluating `window.pbSetPushProgress({ components:{done,total,current}, screens:{done,total,current} })` in the preview so the user sees the bars advance in the UI Design tab; the chat ticks are the source of truth.

**Roll-forward only:** on partial failure, persist every node ID written; the next push reconciles via G-FP2. Never roll back.

## Gate G-FP6 — Render audit (mandatory; blocks Step 7)
The push is **not done** until this passes. After Step 6, re-read the pushed result from Figma — `Figma:get_metadata` on `rootFrameId` and every created component/screen, plus `Figma:get_screenshot` of the root — and assert EVERY invariant below. This is a **deterministic, machine-checkable** audit, not an eyeball pass. If ANY invariant fails → **HARD FAIL**: do NOT run Step 7, do NOT report the push as done; name the exact node + failing invariant and stop (roll-forward — written nodes stay for the next push to reconcile via G-FP2).

| # | Invariant (all must hold) |
|---|---|
| 1 | **Auto-layout everywhere** — every created frame / component / screen has `layoutMode ≠ NONE`. |
| 2 | **Zero absolute children** — no created node has a child with `layoutPositioning = 'ABSOLUTE'`. |
| 3 | **Zero raw values** — every fill / stroke / corner radius / itemSpacing / padding on a created node is **bound to a variable** (no raw hex, no arbitrary px) — color, space, AND radius. |
| 4 | **Variants in a ComponentSet** — any component with `properties[]` is a `COMPONENT_SET` whose variants match the declared `prop=value` axis. |
| 5 | **Screens = instances** — every library / DS-matched element on a screen is an `INSTANCE` (has `mainComponent`), never a local copy. |
| 6 | **Token coverage** — bound-variable count ≥ the G-FP3 token union; no in-scope token left unbound. |
| 7 | **Nested globals = instances** — every component `anatomy.parts[]` entry with an `orgId` resolves to an `INSTANCE` (has `mainComponent`) of that global's DS match inside the built component (in EVERY variant), never a redrawn local frame/text. Verifiable offline over the two committed contracts: `python3 tools/lint_registry.py --figma registry.json figma-transfer.json`. |

Print the result as a ✅/❌ checklist (one row per invariant + counts). Only an **all-✅** result proceeds to Step 7.

## Step 7 — Update contracts + log (only after G-FP6 passes all invariants)
- **`figma-transfer.json`** — new `components[<id>].figmaComponentSetId`/`figmaId`, `components[<id>].nestedInstances` (one entry per nested-global `orgId`: `{instanceId, componentKey, dsName}`), `screens[<id>].figmaFrameId`/`elementMapping`, `components[<id>].dsMatch`; `lastPushedAt`, `lastPushedHash[<scope>]`, `lastScope`.
- **`registry.json`** — write the Figma IDs back onto the matching `components[]` / `screens[]` entries (`figmaId`, `figmaComponentSetId`, `dsMatch`, `figmaFrameId`) and **only** those keys. Re-read to confirm valid JSON; on parse failure, restore and report — never leave a broken registry.
- **Push log** — append the plan + Figma responses + the contract diff to `memory/figma-pushes/<ISO-timestamp>.log`.

Confirm to the user with the counts and the contracts updated. Re-running without changes is a no-op (content-hash deduped); `--force` to re-push.

## NEVER rules (ported)
- NEVER push without a target (stop at G-FP1).
- NEVER coerce a token to a raw value — unmapped = pause at G-FP3.
- NEVER overwrite a Figma node not tracked in `figma-transfer.json` (it was designer-created).
- NEVER publish to the team library (a designer action in the Figma UI).
- NEVER push if the in-scope hash matches the last push, unless `--force`.
- NEVER auto-add a variant axis (surfaces as `axis-change` in G-FP2).
- NEVER push > 1 screen or 5 components without `--batch`.
- NEVER roll back on partial failure — roll-forward only.
- NEVER mutate a bound `dsMatch` without `--rematch`.
- NEVER attempt bi-directional sync (one-way only; warn at G-FP5 if Figma is newer).
- NEVER skip Step 7's `registry.json` write-back (without identity, the next push duplicates).
- NEVER hardcode a design-system name — always read `dsMatch.library` from config.
- NEVER position a frame child absolutely — auto-layout on every frame (R3).
- NEVER hand-emit / hand-draw prototype content into Figma outside this command — every export runs these gates.
- NEVER redraw a nested global as a local frame — an `anatomy.parts[]` entry with an `orgId` MUST be instanced from the global's DS match (G-FP6 inv #7); baking it in is a hard fail.
- NEVER run Step 7 or report a push "done" while any G-FP6 invariant fails — the render audit is a hard completion gate.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
