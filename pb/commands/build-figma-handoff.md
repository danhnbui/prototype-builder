---
description: Sub-command of /pb:build. One-way registry → Figma transfer via the GHN DS Bridge plugin (declarative node JSON), with a clarify pass (G-FP0–G-FP5) then an offline render audit (G-FP6) on the emitted node JSON. Default is BRIDGE mode: emit node JSON to paste into the plugin's Code → Figma tab (deterministic, offline, linked instances). The Figma MCP is a read-only CONTEXT provider (match/enrich), never the writer; the legacy MCP write path stays behind --mcp (deprecated). DS-neutral. Auto-layout on every frame (R3). One-way.
---

# /pb:build-figma-handoff

Push the prototype's components and screens to Figma. Reads from **`registry.json`**
(`components[]` / `screens[]`) — the same composition tree the prototype renders from — and the DS
**catalog** (`design-system/<name>/ds-catalog.json`, the publish keys/variables from the GHN DS
Bridge *Scan DS*, cloned by `/pb:pull-ds`). **DS-neutral:** the library is read from
`memory/constitution.md` → Design System Lock, mirrored in `figma-transfer.json.dsMatch.library`.

> **How the push happens (BRIDGE mode, default).** `pb/tools/registry_to_figma.py` deterministically
> lowers the registry to **GHN DS Bridge node JSON** (~0 model tokens — a token lever). You paste it
> into the plugin's **Code → Figma** tab; the plugin rebuilds it as real, **linked component
> INSTANCES**. Because the registry is a machine-readable composition tree (component-first / atomic),
> the lowering is 1:1: every screen element is an INSTANCE of its DS component's publish key. pb never
> hand-emits Figma nodes and never depends on a write-time MCP connection.
>
> **The Figma MCP is a CONTEXT provider only** — used at G-FP3/G-FP4 to *propose* token/component
> matches (`search_design_system`, `get_variable_defs`, `get_screenshot`) when the catalog is thin.
> It never writes. The legacy MCP write path is retained behind `--mcp` (deprecated).

## User input
```text
$ARGUMENTS
```
| Flag | Default | Effect |
|---|---|---|
| `--scope=components\|screens\|both` | ask in G-FP0 | What to push |
| `--screen=<id>` | all in scope | Restrict screens push to one screen |
| `--component=<id>` | all in scope | Restrict components push to one component |
| `--out=<path>` | `figma-nodes.json` | Where to write the emitted node JSON (bridge mode) |
| `--batch` | refuse if >1 screen or >5 components | Allow large pushes |
| `--dry-run` | false | Run all gates + show the plan, emit nothing |
| `--force` | false | Skip the no-op hash check (G-FP1.5) |
| `--rematch` | false | Re-prompt DS matches even for already-bound components |
| `--mcp` | false | **Legacy**: use the Figma MCP `use_figma` write path instead of the plugin (deprecated) |

## Gate G-FP0 — Scope selection
If `--scope` is absent, ask (1 components · 2 screens · 3 both). Save to `figma-transfer.json.lastScope`.

## Gate G-FP1 — Pre-flight integrity (always runs)
Sequential. ANY failure → HARD FAIL with the exact message; nothing emitted.
1. **DS catalog present** — confirm `design-system/<name>/ds-catalog.json` exists (the Scan DS publish
   keys/variables). On absence → HARD FAIL: `No DS catalog. Run /pb:pull-ds (with the GHN DS Bridge Scan DS output) first.` *(In `--mcp` mode this check becomes "Figma MCP reachable — call `whoami`" instead.)*
2. **Registry loaded** — `registry.json` parses and has `components[]` / `screens[]`. Empty → HARD FAIL: `registry.json has no components/screens. Run /pb:build first.`
3. **`figma-transfer.json` exists OR seed it** — if absent, seed from `figma-transfer.template.json`; set `dsMatch.library` to the Design System Lock name.
4. **No-op detection (G-FP1.5)** — SHA-256 the in-scope slice; if it equals `lastPushedHash[<scope>]` and `--force` absent → STOP (`✓ No changes since last push.`).

*(In `--mcp` mode only, also resolve the target file/page/root frame as before — the bridge builds on the plugin's current page, so no target is needed.)*

## Gate G-FP2 — Identity audit (per scope)
- **components / both:** each component with a `dsKey` in `figma-transfer.json` → `bound` (reference); else `unmatched` (needs G-FP4). A component that maps to a DS key is a **reference**, not a local build.
- **screens / both:** always emitted as root frames of INSTANCEs (screens have no Figma identity in bridge mode — the plugin builds fresh each paste).
- **Affected-screen analysis:** for each changed component, list the screens that reference it (`screens[].elements[].orgId === <id>`) so the blast radius is explicit.

Output the audit (bound / unmatched / local counts + ids + affected screens) and ask `Proceed to G-FP3? (yes / cancel)`.

**Batch guard:** if in-scope screens > 1 OR components > 5 and `--batch` absent → HARD FAIL.

## Gate G-FP3 — Token resolution (always runs)
Collect every token reference in scope — the **union** of component `anatomy.parts[].token.name` + `spec.stack[]`, screen `elements[].tokens[]`, and every `var(--name)` in the in-scope render body files (`renderSrc`). Load `figma-tokens.json`. Resolve each token to a Figma **variable** from, in order: (a) `figma-tokens.json`, (b) the **ds-catalog** `variables[]` by name, (c) an MCP `search_design_system` / `get_variable_defs` proposal (context only). Pause:
```
⏸ TOKEN MAPPING NEEDED
  brand      → {DS} Colors/brand      (var_brand)     [catalog]
  space-4    → {DS} Spacing/4         (var_space_4)   [catalog]
  custom-orange → NO MATCH                            [gap — stays numeric + flagged]
Accept all?  (yes / edit / cancel)
```
On `yes` → save to `figma-tokens.json`. A no-match is a **gap** (never coerced to raw): the transformer emits the numeric fallback + a `<prop>Token` sidecar and logs it to `gaps.md`.

## Gate G-FP4 — DS component match (components or both only)
Skip if scope is `screens`. For each `unmatched` component: resolve its DS publish key from, in order: (a) `figma-transfer.components[<id>].dsKey`, (b) the **ds-catalog** `components[]` by `dsMatch.component` / name / id, (c) an MCP `search_design_system` proposal (context only). Pause:
```
⏸ DS COMPONENT MATCH   (library: {DS})
  text-input → {DS} Input     (key 10:200)   [catalog]
  button     → {DS} Button    (key 10:100)   [catalog]
  alert-banner → NO MATCH                    [local build from anatomy]
Accept all?  (yes / edit / cancel)
```
On `yes` → save `figma-transfer.components[<id>].dsKey` + `propertyMapping`. NO-MATCH → the transformer emits a **local FRAME from anatomy** (parts with an `orgId` nested as INSTANCEs) + a gap. Never invent a key.

## Gate G-FP5 — Emit plan + confirmation
Output the full plan: scope · library · components (reference-by-key / local-build) · screens (root frames of INSTANCEs) · tokens (bound / gap) · the auto-layout policy (R3: every frame auto-layout). Ask `Proceed to emit? (yes / no / show-detail)`. If `--dry-run` → print and STOP. *(This gate is not "irreversible" in bridge mode — emitting node JSON writes nothing to Figma. The irreversible act is you pasting it into the plugin.)*

## Step 6 — Emit (BRIDGE mode; only after G-FP5 `yes`)
Run the deterministic transformer (load the `figma-use` bridge skill first for the authoring rules):
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/registry_to_figma.py" registry.json \
  --scope <scope> [--screen <id>|--component <id>] \
  --catalog design-system/<name>/ds-catalog.json \
  --tokens figma-tokens.json --transfer figma-transfer.json \
  --out <out> --gaps gaps.md
```
It emits `{ meta, roots[], gaps[] }`: each screen → a root FRAME (auto-layout from `layout`) of element **INSTANCEs** (by DS key + `componentProperties` from the element's props/state); each local component → a FRAME with its anatomy parts nested as INSTANCEs; spacing → numeric + a `<prop>Token` variable sidecar. **Hand the user the exact steps:** open the GHN DS Bridge plugin → **Code → Figma** tab → paste `<out>` → **Build / Run**. Report the gap list (unmatched components/tokens) plainly.

*(Legacy `--mcp` mode: instead run the ordered `Figma:use_figma` writes as before — tokens → components → screens → bindings — per the deprecated MCP rituals. Retained for environments without the plugin.)*

## Gate G-FP6 — Render audit (split: offline blocks the emit; round-trip verifies the paste)
**Offline (mandatory, before handing over the JSON — deterministic, machine-checkable on `<out>`):**

| # | Invariant (must hold on the emitted node JSON) |
|---|---|
| 1 | **Auto-layout everywhere** — every FRAME has `layout.mode ≠ NONE`. |
| 2 | **Zero absolute children** — no node uses absolute positioning. |
| 4 | **Variants as component props** — each INSTANCE's `componentProperties` match the DS component's declared axes (from the catalog). |
| 5 | **Screens = instances** — every screen element is an `INSTANCE` carrying a `component.key` (component-first), never inlined markup. |
| 7 | **Nested globals = instances** — every local component's `anatomy.parts[]` with an `orgId` is a nested `INSTANCE` (instance, don't bake). |

`tests/r4_figma_bridge.py` asserts 1/2/4/5/7 on the transformer output; a build session can also eyeball `<out>`. Any failure → do NOT hand over the JSON; fix the registry/mapping and re-emit.

**Round-trip (optional, verifies the actual paste — invariants 3/5/6 need the built result):** after you paste + Build, serialize the built frame back (plugin *Figma → Code*), paste it to pb, and pb diffs it against `<out>` — confirming spacing/radius/color are **variable-bound** (inv #3, once the plugin's spacing-binding fix from `docs/figma-bridge-plugin.md` is applied), every element resolved to a real instance (inv #5), and token coverage (inv #6). Report the diff.

## Step 7 — Update contracts + log (after the offline audit passes)
- **`figma-transfer.json`** — `components[<id>].dsKey` + `propertyMapping`, `nestedInstances`, `lastPushedAt`, `lastPushedHash[<scope>]`, `lastScope`. (Bridge mode records **portable keys**, not file-local node ids.)
- **`figma-tokens.json`** — the accepted token → variable `{name,key}` map from G-FP3.
- **`registry.json`** — bridge mode writes back NOTHING to the registry (the plugin builds locally; there are no Figma node ids to record). *(Only `--mcp` mode writes `figmaId`/`figmaFrameId` back.)*
- **Push log** — append the plan + emitted node count + gaps + contract diff to `memory/figma-pushes/<ISO-timestamp>.log`.

Confirm counts + the contracts updated. Re-running without changes is a no-op (content-hash deduped); `--force` to re-emit.

## NEVER rules
- NEVER invent a DS publish key or a variable — an unmatched component/token is a **gap** (local build / numeric fallback + `gaps.md`), never a fabricated reference.
- NEVER coerce a token to a raw value — unmapped = pause at G-FP3, then a flagged gap.
- NEVER auto-add a variant axis (surfaces as its own group in G-FP2).
- NEVER push > 1 screen or 5 components without `--batch`.
- NEVER hardcode a design-system name — read `dsMatch.library` from config.
- NEVER emit a non-auto-layout frame or an absolutely-positioned child (R3) — the transformer sets `layout.mode` on every frame by construction.
- NEVER redraw a nested global as a local frame — an `anatomy.parts[]` `orgId` MUST be a nested INSTANCE (G-FP6 inv #7).
- NEVER hand over node JSON while an offline G-FP6 invariant fails.
- NEVER write to Figma from pb in bridge mode — pb emits JSON; the plugin (driven by the user) is the only writer. In `--mcp` mode the write goes through the (deprecated) MCP path.
- NEVER attempt bi-directional sync (one-way only).

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
