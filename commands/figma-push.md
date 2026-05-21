---
description: Push from PB_DATA to a target Figma file via the Figma MCP. One command with --scope=components|screens|both. Runs a 5-gate clarify pass (G-FP0 through G-FP5) before any irreversible Figma write. v1 is one-way only; bi-directional sync is out of scope.
handoffs:
  - label: Audit Drift Before Next Push
    agent: speckit.prototype-builder.check-drift
    prompt: Run a drift audit across the trio before the next figma-push to catch contradictions early.
  - label: Sync Tab 4-Screen From Latest Push
    agent: speckit.prototype-builder.handoff
    prompt: Refresh Tab 4-Screen with the latest screen IDs after a successful push.
---

## User Input

```text
$ARGUMENTS
```

Supported flags (parse from `$ARGUMENTS`):

| Flag | Default | Effect |
|---|---|---|
| `--scope=components\|screens\|both` | ask in G-FP0 | What to push |
| `--screen=<id>` | all in scope | Restrict screens push to one screen |
| `--organism=<id>` | all in scope | Restrict components push to one organism |
| `--batch` | refuse if >1 screen or >5 organisms | Allow large pushes |
| `--dry-run` | false | Run all gates + show plan, skip actual Figma writes |
| `--force` | false | Skip the no-op hash check (G-FP1.5) |
| `--rematch` | false | Re-prompt DS matches even for already-bound organisms |

## Gate G-FP0 — Scope selection

If `--scope` not in `$ARGUMENTS`, ask:

```
What's the push scope?
  1) components — push Tab 4-Component organisms as a Figma component library
  2) screens    — push Tab 4-Screen frames using existing components
  3) both       — components first, then screens consume them as instances

Choose 1-3:
```

Wait for prompt + Enter. Save the choice to `figma-transfer.json` under `lastScope` so re-runs can short-circuit.

## Gate G-FP1 — Pre-flight integrity (always runs)

Sequential checks. ANY failure → HARD FAIL with the exact error message; no Figma writes happen yet.

### Check 1.1 — Figma MCP reachable
Call `Figma:whoami`. On error → HARD FAIL:
```
Figma MCP not reachable. Confirm the Figma connector is configured at https://mcp.figma.com and re-run.
```

### Check 1.2 — Template + PB_DATA loaded
Read `./prototype/template.html`. Grep for `const PB_DATA = {`. If missing → HARD FAIL:
```
PB_DATA not found in template.html. Run /speckit-prototype-builder-build to populate it first.
```

### Check 1.3 — figma-transfer.json exists OR seed it
If `./figma-transfer.json` doesn't exist, prompt:
```
No figma-transfer.json found. To push, this command needs a target Figma file.

Paste the Figma file URL:
```
Wait for URL. Validate the format (must match `https://www.figma.com/file/<key>/...` or `https://www.figma.com/design/<key>/...`). Extract `<key>` as `fileKey`. Write `./figma-transfer.json` from the template shape (see `figma-transfer.template.json`).

### Check 1.4 — Target page + root frame
If `target.pageId` is null in figma-transfer.json:
- Call `Figma:get_metadata` for the file
- List pages; prompt: `"Which page should pushes land on?"`
- Save `pageId` + `pageName` to figma-transfer.json
- Then prompt: `"Create a new root frame named '<feature> — pushed from PB' OR pick an existing root?"`
- Save `rootFrameId` + `rootFrameName` to figma-transfer.json

### Check 1.5 — No-op detection
Compute SHA-256 of the relevant slice of `PB_DATA` for the chosen scope:
- `components` → hash `PB_DATA.handoff.organisms`
- `screens` → hash `PB_DATA.handoff.screens`
- `both` → hash both

Compare to `figma-transfer.json.lastPushedHash[<scope>]`. If equal AND `--force` is not in args → STOP:
```
✓ No changes since last push. Nothing to do.

Last successful push: <ISO date>
Scope:                <scope>
Target:               <fileUrl>

Pass --force to push anyway.
```

## Gate G-FP2 — Identity audit (per scope)

### For scope `components` or `both`:
For each organism in `PB_DATA.handoff.organisms`:
- If `organisms[<id>].figmaComponentSetId` is set in figma-transfer.json → mark `update`
- If not → mark `new`

### For scope `screens` or `both`:
For each screen in `PB_DATA.handoff.screens`:
- If `screens[<id>].figmaFrameId` is set → mark `update`
- If not → mark `new`

### Variant-axis change detection (components only)
For each `update` organism, compare `properties[]` in PB_DATA to `propertyMapping` in figma-transfer.json. If a new property appeared OR an existing property gained new option values → flag as `axis-change`. NEVER auto-add a variant axis — these MUST appear in the G-FP2 batch confirmation as a separate group.

### Batch confirmation
Output:
```
Identity audit (scope: <scope>):

  New organisms (CREATE):       <count>
    - <id> (<name>)
  Updated organisms:            <count>
  Organisms with axis changes:  <count>
    - <id> — added property '<prop>' with options [...]

  New screens (CREATE):         <count>
  Updated screens:              <count>

Total Figma writes (estimate): <N>

Proceed to G-FP3?  (yes / cancel)
```

Wait for confirmation. On `cancel` → stop, no further gates run.

### Batch size guard
If (new screens + updated screens) > 1 OR (new organisms + updated organisms) > 5, AND `--batch` is NOT in args → HARD FAIL:
```
Batch size exceeded. <X> screens and <Y> organisms queued; default limit is 1 screen / 5 organisms per push.
Re-run with --batch to override, or scope down with --screen=<id> / --organism=<id>.
```

## Gate G-FP3 — Token resolution (always runs)

Collect every token reference from the active scope:
- Organisms: every `anatomy.parts[].token.name` + every `spec.stack[]` token reference
- Screens: every `elements[].tokens[].name`

Load `./figma-tokens.json`. For each unique token name:
- If in `tokens` map → use the mapping
- If not → propose via `Figma:search_design_system` with a query built from the token name (e.g., `--brand` → search "brand color")

For unmapped tokens with a proposed match:
```
⏸ TOKEN MAPPING NEEDED

The following tokens are not in figma-tokens.json. Proposed mappings:

  --brand           → HIVE/Colors/brand              (VariableID:5:34)  [match by name]
  --text-secondary  → HIVE/Colors/text/secondary     (VariableID:5:35)  [match by name]
  --custom-orange   → NO MATCH FOUND                                     [will create local]

Accept all proposed?  (yes / edit / cancel)
```

On `yes` → save mappings to figma-tokens.json. Continue.
On `edit` → enter per-token correction mode (paste correct VariableID or skip).
On `cancel` → stop.

For NO-MATCH tokens:
- Default: create as a local variable in a collection named `Prototype tokens`
- User can override per token: `skip / map to existing (paste ID) / create in a different collection`
- These choices are persisted to figma-tokens.json so future pushes don't re-ask.

## Gate G-FP4 — DS component match (components or both only)

Skip if scope is `screens` only.

For each `new` organism from G-FP2:
- If `PB_DATA.handoff.organisms[<id>].dsMatch.figmaComponentId` is already set AND `--rematch` not in args → use it (instance-swap to HIVE component)
- Otherwise → propose via `Figma:search_design_system` with the organism's `name`

Output:
```
⏸ DS COMPONENT MATCH

Proposed HIVE matches (these are persisted to figma-transfer.json — verify before commit):

  text-input        → HIVE/Forms/Text input          (5678:910)
  primary-button    → HIVE/Buttons/Primary           (5678:920)
  alert-banner      → NO MATCH FOUND                                  [will create local]

Accept all?  (yes / edit / cancel)
```

On `yes` → save matches to figma-transfer.json `organisms[<id>].dsMatch`. Continue.
On `edit` → per-organism correction (paste a different componentId, OR explicitly mark "create local — don't match").
On `cancel` → stop.

NO-MATCH organisms default to **create local** — written into the file under the chosen root frame, not into HIVE. This decision is persisted; future pushes update in place rather than re-asking.

## Gate G-FP5 — Push plan + confirmation (irreversible)

Output the complete plan. **THIS IS THE ONLY GATE FOR THE IRREVERSIBLE WRITE.**

```
═══════════════════════════════════════════════
  FIGMA PUSH PLAN
═══════════════════════════════════════════════

Scope:    <components | screens | both>
Target:   <fileUrl>
Page:     <pageName> (<pageId>)
Root:     <rootFrameName> (<rootFrameId>)

COMPONENTS to create as local (N):
  - alert-banner          → 2 variants (state: default/error)
  - product-card          → 3 variants (size: sm/md/lg)

COMPONENTS to update (M):
  - text-input            → 1 axis change (state: add 'success')

COMPONENTS to instance-swap to HIVE (K):
  - email-field           → HIVE/Forms/Text input  (5678:910)
  - sign-in-btn           → HIVE/Buttons/Primary   (5678:920)

SCREENS to create (X):
  - sign-in               (rootFrame.children[+1])
  - register              (rootFrame.children[+2])

SCREENS to update (Y):
  - otp-verify            (existing frame 1:50, 3 element changes)

TOKENS to bind: 7 (all mapped to existing variables)
TOKENS to create: 1 (--custom-orange → local in 'Prototype tokens' collection)

Auto-layout heuristic:
  - Default sizing axis for unannotated frames: hug-V, fill-H
  - Frames with explicit `sizing.width`/`sizing.height` use those values

═══════════════════════════════════════════════
Estimated Figma writes: <total>
Dry-run mode:           <true | false>
═══════════════════════════════════════════════

Proceed?  (yes / no / show-detail)
```

On `yes` → execute Step 6.
On `no` → stop, no writes, no contract updates.
On `show-detail` → expand the plan with full payload per node (props, tokens, layout config), then re-ask.

If `--dry-run` is in args, STOP HERE — print the plan and exit. No writes, no contract updates.

## Step 6 — Execute push (only after G-FP5 yes)

Order matters for dependency resolution. Each sub-step is a separate `Figma:use_figma` call (or several).

1. **Create/update tokens**
   - For each `create-local` token from G-FP3: call Figma MCP to create the variable in the chosen collection
   - For each existing mapping: no write needed, just record the binding
   - Capture returned VariableIDs into figma-tokens.json

2. **Create/update components** (skip if scope = `screens`)
   - For each `create-local` organism: build the Figma component from PB_DATA's `anatomy.parts[]` + `spec.stack[]` + `properties[]`
   - For each `update` organism: apply the diff (new variants, new properties, changed defaults)
   - For each HIVE-matched organism: no write — just record the binding in figma-transfer.json
   - Capture returned componentSetId + componentId per organism

3. **Create/update screens** (skip if scope = `components`)
   - For each new screen: create a frame inside `rootFrameId`, named per `PB_DATA.handoff.screens[<id>].name`
   - For each element in the screen's `elements[]`: create a child node, apply auto-layout per the sizing heuristic, position per the existing render's `data-handoff-el` measurements
   - For HIVE-matched element components: insert as instance, not as local copy
   - Capture returned frameId + elementId map

4. **Apply token bindings**
   - For each element with a token reference, bind the computed-style property to the VariableID from figma-tokens.json
   - Use the Figma MCP variable-binding API

5. **Apply component instance bindings**
   - For each instance binding from step 2/3, ensure the instance points to the correct HIVE library component (not a local copy)

**Roll-forward policy**: if a step fails partway, capture every node ID written up to that point — don't roll back. The next push will reconcile via Identity audit (G-FP2) and treat the partial state as a baseline.

## Step 7 — Update contracts + log

After Step 6 completes (or partially completes):

### Update figma-transfer.json
- New `organisms[<id>].figmaComponentSetId` + `figmaId` per created/updated component
- New `screens[<id>].figmaFrameId` + `elementMapping` per created/updated screen
- New `organisms[<id>].dsMatch` per HIVE match made during this push
- Update `lastPushedAt` to current ISO timestamp
- Update `lastPushedHash[<scope>]` to the SHA-256 from G-FP1.5
- Update `lastScope` to the chosen scope

### Update PB_DATA in template.html
Use the Edit tool with the `const PB_DATA = {` anchor (mirror the safe pattern from `commands/sync-tab2.md` Step 3.5):
- Set `organisms[N].figmaId` + `figmaComponentSetId` + `dsMatch`
- Set `screens[N].figmaFrameId`
- DO NOT touch any other PB_DATA keys

After the edit, re-read the block to confirm it's still syntactically valid JS. If not, restore the previous value and report the parse error — do not leave a broken template.

### Write push log
Append to `.specify/memory/figma-pushes/<ISO-timestamp>.log`:
- The full G-FP5 plan
- The Figma MCP responses (success + IDs)
- Any errors with node-level detail
- The final figma-transfer.json diff (before → after)

## Confirm to user

```
✅ Figma push complete.

Scope:                 <scope>
Target:                <fileUrl>
Page:                  <pageName>
Root frame:            <rootFrameName>

Components created (local):    <count>
Components instance-swapped:   <count>
Components updated:            <count>
Screens created:               <count>
Screens updated:               <count>
Tokens bound:                  <count>
Tokens created (local):        <count>

Contracts updated:
  - figma-transfer.json
  - figma-tokens.json
  - PB_DATA in template.html
  - .specify/memory/figma-pushes/<file>.log

Re-running this command without changes is now a no-op (deduped by content hash). Pass --force to re-push.
```

## Important rules

- **NEVER push without a target.** If figma-transfer.json has no target.pageId / rootFrameId, the command stops at G-FP1 with an actionable error.
- **NEVER coerce a token to a raw value.** Unmapped token = pause at G-FP3, no silent fallback to literal hex/px.
- **NEVER overwrite a Figma node not tracked in figma-transfer.json.** That node was designer-created; the tool refuses to claim ownership.
- **NEVER publish to the team library.** Library publishing is a designer action in the Figma UI — out of scope for v1.
- **NEVER push if the PB_DATA hash matches the last successful push** unless `--force` is in args.
- **NEVER auto-add a variant axis.** Variant changes surface as `axis-change` in G-FP2 and require explicit user confirmation.
- **NEVER push more than 1 screen or 5 organisms without `--batch`.** Protects against runaway pushes during iteration.
- **NEVER roll back on partial failure.** Roll-forward only; node IDs from successful steps are persisted so the next push reconciles.
- **NEVER overwrite figma-tokens.json without preserving the `unresolved[]` list.** That list is the user's debugging trail.
- **NEVER mutate `dsMatch` on an already-bound organism without `--rematch` in args.** Once bound, future pushes update in place.
- **NEVER attempt bi-directional sync.** If figma-transfer.json shows a `figmaModifiedAt` newer than `lastPushedAt`, the tool surfaces a warning at G-FP5 and asks the user to either accept the overwrite or skip. No three-way merge.
- **NEVER skip Step 7's PB_DATA write.** Without the write-back, the next push has no identity and will create duplicates.
