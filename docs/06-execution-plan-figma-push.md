# 06 — Execution Plan: Figma Push (v0.4.0)

**Purpose**: Step-by-step buildout of `/speckit-prototype-builder-figma-push` and the v0.4.0 release of `spec-kit-extension-prototype-builder`. Claude Code reads this and executes phase by phase. STOP at every HITL gate.

**Status**: Ready for Phase 0 confirmation
**Target version**: `spec-kit-extension-prototype-builder@v0.4.0`
**Estimated effort**: ~5 focused hours + Danh-side prework
**Authority**: Danh approves at HITL gates; Claude Code executes everything else

---

## How to read this file

- Phases execute in order. Within a phase, tasks usually sequence; `[P]` marks parallelizable.
- Every task has: Inputs / Outputs / Acceptance / Dependencies / HITL gate / Effort.
- STOP at every HITL gate. Never proceed without explicit "yes" from Danh.
- Default behavior: stop more often, not less.

---

## Phase summary

| Phase | Owner | Description | Effort | Blocks next? |
|---|---|---|---|---|
| 0 | Danh | Pre-flight: Figma MCP, throwaway file, bundle accessible | 30 min | Yes |
| 1 | CC | Drop bundle into extension repo, wire into `extension.yml` | 45 min | Yes |
| 2 | CC | Extend `PB_DATA` in `assets/template.html` (3 nullable keys) | 1 h | Yes |
| 3 | CC | Add Step 9 to `commands/scaffold.md` | 30 min | No |
| 4 | CC | Add Push CTAs to Tab 4-Component + Tab 4-Screen | 30 min | No |
| 5 | Joint | Smoke test against throwaway Figma file (the 7-point test) | 1.5–2 h | Yes |
| 6 | Joint | Ship: commit, tag v0.4.0, push, update `IMPLEMENTATION-NOTES.md` | 15 min + decision | Final gate |

---

## Phase 0 — Pre-flight (Danh's side task)

This phase blocks everything. Claude Code MUST NOT start Phase 1 until G-FX0 fires.

### Task 0.1 — Confirm Figma MCP is reachable

- **Inputs**: Danh's Claude Code session, Figma MCP connector configured
- **Outputs**: Successful `Figma:whoami` call returns identity
- **Acceptance**: `Figma:whoami` returns a name + email, not an auth error
- **Dependencies**: none
- **HITL gate**: none (one console check)
- **Effort**: 5 min

### Task 0.2 — Create throwaway Figma test file with HIVE attached

- **Inputs**: Danh's Figma account; HIVE library accessible
- **Outputs**: A new Figma file at a known URL, HIVE design system enabled in Libraries panel
- **Acceptance**: Opening the file shows HIVE components in Assets panel; can drag-instance one
- **Dependencies**: 0.1
- **HITL gate**: none
- **Effort**: 10 min

### Task 0.3 — Prepare target project for testing

- **Inputs**: Either an existing prototype project OR a fresh dir for scaffold
- **Outputs**: A project directory with `./prototype/template.html` populated with at least 1 organism and 1 screen in `PB_DATA`
- **Acceptance**: Opening `template.html` in browser shows the prototype + component drawer works
- **Dependencies**: 0.1
- **HITL gate**: none
- **Effort**: 10 min (existing project) or 30 min (fresh scaffold)

### Task 0.4 — Verify bundle accessibility

- **Inputs**: The `figma-push-bundle/` folder produced in the previous conversation
- **Outputs**: Confirmation that the 4 files are accessible at a known path
- **Acceptance**: Danh can `ls <path>/figma-push-bundle/` and see all 4 files (`commands/figma-push.md`, `figma-transfer.template.json`, `figma-tokens.template.json`, `README-figma-push.md`)
- **Dependencies**: none
- **HITL gate**: none
- **Effort**: 2 min

### 🛑 HITL Gate G-FX0

Danh confirms in chat: **"Pre-flight done. Phase 1 unlocked."** Include:
- Figma test file URL
- Target project path
- Bundle path

→ Phase 1 unlocked.

---

## Phase 1 — Integrate bundle into extension repo

### Task 1.1 — Copy bundle files into extension repo

- **Inputs**: bundle path + extension repo path (both from G-FX0)
- **Outputs**:
  - `<ext-repo>/commands/figma-push.md`
  - `<ext-repo>/assets/figma-transfer.template.json`
  - `<ext-repo>/assets/figma-tokens.template.json`
- **Acceptance**: All 3 files exist at correct paths; `sha256` matches bundle source
- **Dependencies**: G-FX0
- **HITL gate**: G-FX1
- **Effort**: 5 min

```bash
cp <bundle>/commands/figma-push.md <ext-repo>/commands/
mkdir -p <ext-repo>/assets
cp <bundle>/figma-transfer.template.json <ext-repo>/assets/
cp <bundle>/figma-tokens.template.json <ext-repo>/assets/
```

### Task 1.2 — Wire into `extension.yml`

- **Inputs**: `<ext-repo>/extension.yml`
- **Outputs**: Updated `extension.yml` with new command entry + version bump
- **Acceptance**: `grep figma-push extension.yml` returns the new entry; version reads `"0.4.0"`
- **Dependencies**: 1.1
- **HITL gate**: G-FX1
- **Effort**: 10 min

Use `str_replace` to add under `provides.commands:`:

```yaml
    - name: "speckit.prototype-builder.figma-push"
      file: "commands/figma-push.md"
      description: "Push PB_DATA components and screens to a target Figma file via the Figma MCP. One command, three scopes (--scope=components|screens|both). Runs a 5-gate clarify pass before any irreversible write."
```

Then bump version: `0.3.17` → `0.4.0`.

### Task 1.3 — Bump `preset.yml` version

- **Inputs**: `<ext-repo>/preset.yml`
- **Outputs**: Version updated to `0.4.0`
- **Acceptance**: `grep version preset.yml` shows `"0.4.0"`
- **Dependencies**: 1.2
- **HITL gate**: G-FX1
- **Effort**: 2 min

### Task 1.4 — Update `README.md` with v0.4.0 changelog [P]

- **Inputs**: `<ext-repo>/README.md`
- **Outputs**: New `**v0.4.0**` entry at the top of the Version section
- **Acceptance**: README's Version section opens with `**v0.4.0**` and a 2-3 line summary of the figma-push feature
- **Dependencies**: 1.2
- **HITL gate**: G-FX1
- **Effort**: 10 min

Insert this exact entry above the existing `**v0.3.17**` entry:

```markdown
- **v0.4.0** — Adds the `/speckit-prototype-builder-figma-push` command for one-way PB_DATA → Figma transfer with HIVE component matching. 5-gate clarify pass (scope, integrity, identity, token mapping, DS match, push confirmation). Persistent contracts in `figma-transfer.json` + `figma-tokens.json`. PB_DATA gains three nullable keys per organism (`figmaId`, `figmaComponentSetId`, `dsMatch`) and one per screen (`figmaFrameId`) — all backwards-compatible. New "Push to Figma" CTAs in Tab 4-Component and Tab 4-Screen. v1 is one-way only; bi-di sync deferred to v0.5.0+. See [`docs/06-execution-plan-figma-push.md`](docs/06-execution-plan-figma-push.md) for the build history.
```

### 🛑 HITL Gate G-FX1

Danh reviews:
- `ls commands/ assets/` shows the new files
- `cat extension.yml` shows the new entry and `0.4.0` version
- `git diff README.md` shows the new changelog entry

Confirm with: **"Phase 1 done. Phase 2 unlocked."**

---

## Phase 2 — Extend PB_DATA in template.html

This is the most surgical phase. Read carefully before editing.

### Task 2.1 — Snapshot `template.html` before any edit

- **Inputs**: `<ext-repo>/assets/template.html`
- **Outputs**: Backup at `<ext-repo>/assets/template.html.pre-v0.4.0.bak`
- **Acceptance**: `diff template.html template.html.pre-v0.4.0.bak` returns no diff
- **Dependencies**: G-FX1
- **HITL gate**: G-FX2
- **Effort**: 5 min

```bash
cp <ext-repo>/assets/template.html <ext-repo>/assets/template.html.pre-v0.4.0.bak
```

### Task 2.2 — Locate the PB_DATA block

- **Inputs**: Snapshotted `template.html`
- **Outputs**: A confirmed line range where `const PB_DATA = {` starts and the matching `}` closes
- **Acceptance**: One and only one `const PB_DATA` occurrence in the file; block can be extracted and parsed as JS
- **Dependencies**: 2.1
- **HITL gate**: G-FX2
- **Effort**: 5 min

Run: `grep -n "const PB_DATA" template.html`

### Task 2.3 — Extend organism shape comment + (if present) default examples

- **Inputs**: PB_DATA block from 2.2
- **Outputs**:
  - The documentation comment for `organisms[]` updated to mention the 3 new keys
  - Any existing seeded example organisms gain `figmaId: null`, `figmaComponentSetId: null`, `dsMatch: null`
- **Acceptance**:
  - The shape comment in `PB_DATA.handoff.organisms` documents the new keys
  - Pre-v0.4.0 PB_DATA without these keys still renders Tab 4 correctly (test: temporarily delete the keys, reload, confirm no console errors)
- **Dependencies**: 2.2
- **HITL gate**: G-FX2
- **Effort**: 20 min

Current `organisms[]` comment (line ~520-ish):

```js
organisms: [],           // [{ id, name, renderFn, meta, properties, codeLayout, code, anatomy, spec, uiLogic, usage }] — /build populates
```

Update to:

```js
organisms: [],           // [{ id, name, renderFn, meta, properties, codeLayout, code, anatomy, spec, uiLogic, usage, figmaId, figmaComponentSetId, dsMatch }] — /build populates first 11; /figma-push populates last 3
```

### Task 2.4 — Extend screen shape comment + (if present) default examples [P]

- **Inputs**: PB_DATA block
- **Outputs**: Each screen in `PB_DATA.handoff.screens[]` gains `figmaFrameId: null` (if seeded examples exist); comment updated
- **Acceptance**: Existing screen renders still work; new key visible in PB_DATA inspection
- **Dependencies**: 2.2
- **HITL gate**: G-FX2
- **Effort**: 10 min

Current screens comment:

```js
screens: [],             // [{ id, name, renderFn, elements: [{id, label, tokens, sizing, state}] }] for Screen view
```

Update to:

```js
screens: [],             // [{ id, name, renderFn, elements: [...], figmaFrameId }] — /figma-push populates figmaFrameId
```

### Task 2.5 — Verify template.html still parses (CRITICAL)

- **Inputs**: Modified `template.html`
- **Outputs**: Browser test passes
- **Acceptance**:
  - File opens in browser without errors
  - All 5 tabs are clickable
  - Tab 4-Component shows the empty state OR the example organism — both without console errors
  - Browser devtools console shows NO `SyntaxError`, `ReferenceError`, or `Uncaught` exceptions
- **Dependencies**: 2.3, 2.4
- **HITL gate**: G-FX2
- **Effort**: 10 min

**If this fails**: restore from `template.html.pre-v0.4.0.bak` and re-attempt with smaller edits. Do NOT proceed.

### 🛑 HITL Gate G-FX2

Danh reviews:
- Browser test passes (Task 2.5)
- `git diff template.html | head -40` shows reasonable shape — only PB_DATA keys + documentation, no other changes
- `template.html.pre-v0.4.0.bak` still exists as rollback

Confirm with: **"Phase 2 done. Phases 3 + 4 can run in parallel."**

---

## Phase 3 — Extend scaffold command

### Task 3.1 — Add Step 9 to `commands/scaffold.md`

- **Inputs**: `<ext-repo>/commands/scaffold.md`
- **Outputs**: New "Step 9 — Seed Figma push contracts" between current Step 8 (Confirm to user) and the `## Important rules` section
- **Acceptance**: `scaffold.md` now has Steps 1-9; Step 9 copies the 2 template files from `assets/` to project root
- **Dependencies**: G-FX2
- **HITL gate**: G-FX3
- **Effort**: 15 min

Insert before the `## Important rules` section:

````markdown
### Step 9 — Seed Figma push contracts

Copy the templates from the extension's `assets/` folder into the project root:

```bash
cp ./.specify/extensions/prototype-builder/assets/figma-transfer.template.json ./figma-transfer.json
cp ./.specify/extensions/prototype-builder/assets/figma-tokens.template.json   ./figma-tokens.json
```

These files start empty. The first run of `/speckit-prototype-builder-figma-push` will prompt for the target Figma file URL and populate them.

If the user opts out (no Figma push planned for this project), they can `rm` both files — `/speckit-prototype-builder-figma-push` will re-seed them on demand.
````

### Task 3.2 — Update scaffold's final "Next steps" message

- **Inputs**: `scaffold.md`
- **Outputs**: The "Next steps" block in Step 8 now mentions `/speckit-prototype-builder-figma-push` as step 8 after `sync-erd`
- **Acceptance**: The "Next steps" list has 8 items; last is `/speckit-prototype-builder-figma-push`
- **Dependencies**: 3.1
- **HITL gate**: G-FX3
- **Effort**: 5 min

Append to the existing "Next steps" list:

```
  8. /speckit-prototype-builder-figma-push  — push to Figma (when ready for handoff)
```

### 🛑 HITL Gate G-FX3

Danh reviews `git diff commands/scaffold.md` to confirm only Step 9 + the Next steps list changed.

Confirm with: **"Phase 3 done."**

---

## Phase 4 — Add Push CTAs to template.html

### Task 4.1 — Add CTA in Tab 4-Component

- **Inputs**: `template.html` (post Phase 2)
- **Outputs**: A new "Push components to Figma →" button rendered at the top of `pbRenderHandoffComponent()`, matching the v0.3.5 copy-popover pattern
- **Acceptance**:
  - Button visible when Tab 4-Component is active
  - Clicking opens the copy popover with the slash command pre-filled
  - The terminal-vs-chat dual format displays correctly
- **Dependencies**: G-FX2
- **HITL gate**: G-FX4
- **Effort**: 15 min

In `pbRenderHandoffComponent()`, insert at the top of the returned HTML (before the `handoff-card-list` div):

```js
<div style="margin-bottom: 16px;">
  <button class="sync-button" onclick="openCopyPopover('/speckit-prototype-builder-figma-push --scope=components', this)">
    Push components to Figma →
  </button>
</div>
```

### Task 4.2 — Add CTA in Tab 4-Screen [P]

- **Inputs**: `template.html`
- **Outputs**: A "Push screens to Figma →" button placed next to the existing "Sync now" button in the sync-bar of `pbRenderHandoffScreen()`
- **Acceptance**:
  - Button visible when Tab 4-Screen is active and screens exist
  - Clicking opens copy popover with `--scope=screens` arg
- **Dependencies**: G-FX2
- **HITL gate**: G-FX4
- **Effort**: 10 min

In the `syncBar` variable inside `pbRenderHandoffScreen()`, add a second button after the existing "Sync now":

```js
<button class="sync-button" onclick="openCopyPopover('/speckit-prototype-builder-figma-push --scope=screens', this)">Push screens to Figma →</button>
```

### Task 4.3 — Verify both CTAs render

- **Inputs**: Modified `template.html`
- **Outputs**: Both buttons functional in browser
- **Acceptance**:
  - Component view shows the components-push button at the top of the card list
  - Screen view shows the screens-push button in the sync-bar
  - Both open the copy popover correctly when clicked
  - The popover shows both terminal slash form and chat-input prompt
- **Dependencies**: 4.1, 4.2
- **HITL gate**: G-FX4
- **Effort**: 5 min

### 🛑 HITL Gate G-FX4

Danh visually confirms both CTAs work in browser.

Confirm with: **"Phase 4 done. Ready for smoke test."**

---

## Phase 5 — Smoke test (the 7-point test)

This is the critical gate. Do NOT proceed to Phase 6 until ALL 7 tests pass.

### Task 5.1 — Run scaffold in throwaway directory

- **Inputs**: Throwaway project dir, the bundle, extension repo path
- **Outputs**: Fresh project with `.specify/`, `.claude/`, `design-system/`, `prototype/template.html`, `figma-transfer.json`, `figma-tokens.json`
- **Acceptance**: All 6 paths exist after scaffold completes; `figma-*.json` files match template shape
- **Dependencies**: G-FX4
- **HITL gate**: G-FX5
- **Effort**: 10 min

### Task 5.2 — Run build to populate PB_DATA minimally

- **Inputs**: Scaffolded project + a 1-screen spec
- **Outputs**: `PB_DATA` in `template.html` has 1 organism (`email-field`) and 1 screen (`welcome`) populated
- **Acceptance**: Tab 4-Component shows the organism card; Tab 4-Screen shows the frame
- **Dependencies**: 5.1
- **HITL gate**: G-FX5
- **Effort**: 20 min

Minimal test spec:
- Story 1 (P1): User enters email, taps "Continue"
- Custom organism: `email-field` (text input with state=default|error)
- Screen: `welcome` (single column: title, email-field, Continue button)

### Task 5.3 — Run figma-push --dry-run

- **Inputs**: `PB_DATA` from 5.2; throwaway Figma file URL from G-FX0
- **Outputs**: Dry-run output showing all 5 gates fire, plan rendered, exits without writes
- **Acceptance**:
  - G-FP0: prompts for scope (or accepts `--scope=both`)
  - G-FP1: prompts for Figma file URL, saves to `figma-transfer.json`
  - G-FP3: proposes token mappings against HIVE
  - G-FP4: proposes DS match for `email-field`
  - G-FP5: shows plan
  - Process exits at G-FP5 because `--dry-run`
  - No nodes created in Figma (confirm visually)
- **Dependencies**: 5.2
- **HITL gate**: G-FX5
- **Effort**: 15 min

### Task 5.4 — Run figma-push (real, not dry-run)

- **Inputs**: Same project, throwaway file URL already saved
- **Outputs**: Components + screen created in Figma; contracts updated
- **Acceptance**:
  - All 5 gates fire (idempotent re-prompts ok or skipped via cache)
  - At G-FP5 user confirms "yes"
  - Figma file now has the new local component + screen frame
  - `figma-transfer.json` has new node IDs (`organisms.email-field.figmaComponentSetId`, `screens.welcome.figmaFrameId`)
  - `figma-tokens.json` has new mappings
  - `template.html` has new `figmaId` fields on the email-field organism; **still parses as JS** (verify in browser)
  - Push log written to `.specify/memory/figma-pushes/<timestamp>.log`
- **Dependencies**: 5.3
- **HITL gate**: G-FX5
- **Effort**: 20 min

### Task 5.5 — Verify Figma file state visually

- **Inputs**: Throwaway file open in Figma
- **Outputs**: Visual confirmation
- **Acceptance**:
  - The root frame named `welcome — pushed from PB` (or similar) exists on the chosen page
  - Inside it: `email-field` instance + Continue button
  - Auto-layout applied (frame collapses correctly to content)
  - Tokens bind correctly (text color, fill color from HIVE — verify via Figma's "Variables" inspect panel)
- **Dependencies**: 5.4
- **HITL gate**: G-FX5
- **Effort**: 10 min

### Task 5.6 — Re-run figma-push with no PB_DATA changes

- **Inputs**: Same project, same `PB_DATA`
- **Outputs**: No-op detection fires
- **Acceptance**:
  - G-FP1.5 outputs `✓ No changes since last push. Nothing to do.`
  - No prompts after G-FP1.5
  - No Figma writes
- **Dependencies**: 5.5
- **HITL gate**: G-FX5
- **Effort**: 5 min

### Task 5.7 — Edit PB_DATA, re-push, verify update-not-duplicate

- **Inputs**: Modified `PB_DATA` — add `state: 'success'` to the email-field variant axis
- **Outputs**: G-FP2 surfaces axis-change; G-FP5 plan shows "update" not "create"
- **Acceptance**:
  - G-FP2 flags `email-field` as `axis-change`
  - G-FP5 shows "Components to update: 1" (NOT "Components to create: 1")
  - After push, Figma file shows the email-field component WITH the new `success` variant (single component, 3 variants — not a duplicate component)
  - `figma-transfer.json` shows updated `propertyMapping` with the new option
- **Dependencies**: 5.6
- **HITL gate**: G-FX5
- **Effort**: 20 min

### 🛑 HITL Gate G-FX5

Danh reviews all 7 test outputs:
- 5.1 → 5.7 all pass with their stated acceptance
- The throwaway Figma file looks correct
- The contract files are populated correctly
- Push log exists and is readable

Confirm with: **"Smoke test passed. Phase 6 unlocked."**

**If any test fails**: STOP, file what failed, iterate on the command body (not the plan). Once command body fixed, re-run failing tests + downstream tests.

---

## Phase 6 — Ship

### Task 6.1 — Update `IMPLEMENTATION-NOTES.md` with the new Delta

- **Inputs**: `<ext-repo>/docs/IMPLEMENTATION-NOTES.md`
- **Outputs**: New "Delta 10 — Figma push added (v0.4.0)" section
- **Acceptance**: Delta 10 explains the new command, the persistent contracts, the v1 constraints, and the deferred bi-di path
- **Dependencies**: G-FX5
- **HITL gate**: G-FX6
- **Effort**: 10 min

Add at the end of the existing Deltas section (after "Delta 9"):

```markdown
## Delta 10 — Figma push added (v0.4.0)

**Docs assume**: No code-to-Figma transfer mechanism in v1; handoff is a documentation-only artifact (Tab 4-Screen renders tokens + sizing but doesn't push to Figma).

**Reality** (as of 2026-05-21): `/speckit-prototype-builder-figma-push` provides one-way PB_DATA → Figma transfer with HIVE component matching. The command runs a 5-gate clarify pass (scope, integrity, identity, token mapping, DS match, push confirmation) before any irreversible write.

**What was added**:
- `commands/figma-push.md` — the command body (5 gates + execution + contract updates)
- `assets/figma-transfer.template.json` — persistent ID map + decisions, seeded at scaffold
- `assets/figma-tokens.template.json` — code-token → Figma-variable mapping, seeded at scaffold
- 4 new PB_DATA keys: `organisms[N].figmaId`, `organisms[N].figmaComponentSetId`, `organisms[N].dsMatch`, `screens[N].figmaFrameId` (all nullable, backwards-compatible)
- 2 new CTAs in `template.html` Tab 4 (component-push and screen-push)
- New Step 9 in `commands/scaffold.md` that seeds the contract files

**v1 constraints (documented in `commands/figma-push.md`)**:
- One-way only (code → Figma); Figma → code reverse is deferred to v0.5.0+
- No library publishing (designer action in Figma UI)
- No multi-breakpoint frames per push (rerun with different `--screen=`)
- No bi-directional sync (deferred to v0.6.0+ — requires 3-way merge)

**Open path**: see `docs/06-execution-plan-figma-push.md` "Bi-di path (deferred)" section for the v0.5.0 → v0.7.0 progression.
```

### Task 6.2 — Commit changes

- **Inputs**: All Phase 1-4 + Phase 6.1 changes in git
- **Outputs**: A single commit (or 2-3 logical commits) with clear messages
- **Acceptance**: `git log --oneline -3` shows the new commits; `git status` is clean
- **Dependencies**: 6.1
- **HITL gate**: G-FX6
- **Effort**: 5 min

Suggested commit message:

```
feat(figma-push): add v0.4.0 — one-way PB_DATA → Figma transfer

- New command /speckit-prototype-builder-figma-push with 3 scopes
- 5-gate clarify pass: integrity, identity, token, DS match, push confirm
- Persistent contracts: figma-transfer.json + figma-tokens.json
- PB_DATA extended with figmaId/figmaComponentSetId/dsMatch (backwards-compat)
- Tab 4 CTAs for component-push and screen-push
- scaffold.md Step 9 seeds the contract files at init
- v1 is one-way only; bi-di sync deferred to v0.5.0+
- 7-point smoke test passed against throwaway file
```

### Task 6.3 — Tag and push

- **Inputs**: Committed changes
- **Outputs**: Tag `v0.4.0` pushed to remote
- **Acceptance**: `git ls-remote --tags origin | grep v0.4.0` returns the ref
- **Dependencies**: 6.2
- **HITL gate**: G-FX6 — **irreversible**
- **Effort**: 5 min

🛑 CRITICAL: Do NOT run `git push` without explicit user approval at G-FX6.

```bash
git tag -a v0.4.0 -m "v0.4.0 — figma-push v1"
git push origin main
git push origin v0.4.0
```

### 🛑 HITL Gate G-FX6 — Ship decision

Danh confirms:
- `IMPLEMENTATION-NOTES.md` Delta 10 is accurate
- Commit message reflects scope honestly
- `v0.4.0` is the right version (not `0.3.18`, not `1.0.0`)
- Ready to push to GitHub

Confirm with: **"Ship v0.4.0."**

After push, the version is permanent. No rollback — only forward (e.g., `v0.4.1` patch if issues found).

---

## What Claude Code must NEVER do

1. **NEVER skip the smoke test** (Phase 5). Even if Phase 4 looks clean, the smoke test is the only place reality is verified.
2. **NEVER push to GitHub without G-FX6 approval**. Tags are permanent; rollback means writing a new tag.
3. **NEVER edit `template.html` without first creating the `.bak` file** (Task 2.1). Phase 2 is the most surgical; rollback must be possible.
4. **NEVER modify the command body** (`commands/figma-push.md` from the bundle) without filing the change as a Phase 5 iteration. The bundle is the agreed contract.
5. **NEVER bump the version past `0.4.0`** in this execution plan. Future versions (`0.4.1`, `0.5.0`, etc.) are separate plans.
6. **NEVER run the actual smoke test (Phase 5) against a production Figma file**. Throwaway file only — verified at G-FX0.
7. **NEVER assume the Figma MCP is connected without G-FX0 confirming it**. Phase 1 onwards depends on it.
8. **NEVER parallelize tasks across phases**. Within a phase, `[P]` tasks parallel. Across phases, sequence.
9. **NEVER continue past a failed acceptance criterion**. Stop, surface, iterate.
10. **NEVER skip the `IMPLEMENTATION-NOTES.md` update** (Task 6.1). The Delta history is how future readers understand why decisions were made.
11. **NEVER push to Figma during Phase 1-4**. Only Phase 5's smoke test writes to Figma — and only against the throwaway file.
12. **NEVER auto-resolve a HITL gate by inferring approval**. Approval must come as text from Danh containing the exact confirmation phrase for that gate.

---

## When to stop and ask Danh

- Any acceptance criterion seems unachievable → propose 2-3 alternatives
- A smoke test (Phase 5) fails 2x in a row → escalate, don't keep iterating blindly
- The Figma MCP behaves unexpectedly (errors, slow, returns wrong shapes) → STOP, document the symptom
- The browser test in Task 2.5 fails → restore from backup, ask Danh
- HITL gate approval doesn't come within ~10 min → ping Danh, don't assume silence = approval
- An effort estimate is exceeded by >2× → stop, re-scope
- You discover a constraint the plan didn't anticipate → file it, ask before working around
- Any error you encounter mentions the words "production", "library publish", or "team-owned" → stop immediately, ask before any further action

Default: stop more often, not less.

---

## Effort summary

| Phase | Min | Max | Includes |
|---|---|---|---|
| 0 | 30 min | 1 h | Danh-side prep |
| 1 | 30 min | 45 min | Bundle integration |
| 2 | 45 min | 1 h | PB_DATA extension (most surgical) |
| 3 | 15 min | 30 min | Scaffold extension |
| 4 | 20 min | 30 min | Template CTAs |
| 5 | 1.5 h | 2 h | Smoke test (the gate) |
| 6 | 15 min | 30 min | Ship |
| **Total** | **~5 h** | **~6 h** | + Danh's gate-review time |

Realistic calendar time: 1-2 days, depending on smoke-test iteration count.

---

## Provenance

This execution plan extends the original `docs/05-execution-plan.md` pattern (v1.0 system buildout, Phases 0-7). It uses identical structure conventions: phase summary table, per-task Inputs/Outputs/Acceptance/Dependencies/HITL/Effort, HITL gates between phases, "What Claude Code must NEVER do" + "When to stop and ask Danh" sections, aggregate effort summary.

Source artifacts produced in the prior conversation turn:
- `commands/figma-push.md` (15.6 KB, 347 lines)
- `figma-transfer.template.json` (1.4 KB)
- `figma-tokens.template.json` (0.8 KB)
- `README-figma-push.md` (7.7 KB)

If you find a contradiction between this plan and the bundle's `commands/figma-push.md`, **the command body wins** — flag it and pause.
