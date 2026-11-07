---
description: The one hand-off command. Asks who is receiving the work, then delivers it — (1) everything including a vendored Product Builder, so they keep building; (3) Figma, lowered deterministically from the registry and written through the Figma MCP, with the DS Bridge plugin as the fallback; (4) tickets for front-end developers, one file per buildable slice in a fixed template, linted, then published one-way to Notion or Jira. Mode 2 (engineering) was retired in v3.0.0 and the numbers were not reused. Replaces the four commands that used to do this: handoff-close, handoff-dev, hand-off and build-figma-handoff.
---

# /pb:handoff

One command for every hand-off. It asks **who is receiving this and what they need to do with
it**, because that — not a flag — decides which files to write.

## User input
```text
$ARGUMENTS
```

| Flag | Default | Effect |
|---|---|---|
| `--mode=1\|3\|4` | **ask** | Skip the question (also `all` · `figma` · `tickets`). `--mode=2` / `dev` and `--tier` are **retired** (v3.0.0, §Retired) |
| `--out <dir>` | per mode | Where to write |
| `--with-recordings` | false | Mode 1: also carry participants' screen and voice recordings. Off by default; ask before using it (§1.2) |
| `--people` / `--context` | — | Mode 1, narrowed: the viewer artifact only / the bundle only |
| `--component <id>` | all | Mode 3: restrict to one component |
| `--scope=components\|screens\|both` | ask (G-FP0) | Mode 3: what to push |
| `--screen=<id>` | all in scope | Mode 3: restrict the screens push |
| `--bridge` | false | Mode 3: emit node JSON to paste, instead of writing through the MCP |
| `--batch` | refuse >1 screen / >5 components | Mode 3: allow a large push |
| `--accept-findings` | false | All modes: continue past a security-scan **error** (exit 2) without asking; the override is recorded in the output (§1b) |
| `--dry-run` | false | Mode 3: run every gate, show the plan, emit nothing |
| `--force` | false | Mode 3: skip the no-op hash check |
| `--rematch` | false | Mode 3: re-prompt DS matches for already-bound components |
| `--ticket <ID>` | all | Mode 4: work on one ticket |
| `--publish notion\|jira\|none` | **ask** | Mode 4: where to publish once the tickets lint clean |

## 0 · Ask (skip only when `--mode` is given)

Ask **once**, as one question with three options, and wait. Do not infer from context — the same
project hands off to all three audiences at different times, and guessing wrong produces a folder
the recipient cannot use. The numbers are 1, 3 and 4: **2 is retired and not reused**, so a
`--mode=3` in an old script or in the design-system site's Push-to-Figma prompt still means Figma.

> **What are you handing off?**
> 1. **Everything, including Product Builder** — they continue the work. The prototype, the full
>    portable bundle, and a vendored copy of the plugin so `/pb:*` works for them on day one.
> 3. **For Figma** — push the components and screens into a Figma file.
> 4. **Tickets for front-end developers** — one ticket per buildable slice, in a fixed template,
>    published to Notion or Jira.

`--mode=2`, `--mode=dev` or `--tier=…` → do not run anything. Print the **Retired** note at the end of
this file and re-ask the question.

## 1 · Contract gate (fail-closed — runs first, every mode)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/lint_registry.py" --strict registry.json
```
Non-zero (any `ERROR`) → **STOP**. Print the findings, tell the user to `/pb:build` and retry. Never
hand off a registry that violates the contract (NS6). Then `/pb:build --render` — never hand off a
stale render.

**DS-drift pre-flight (advisory, never blocks).** If `meta.dsSource` is set, re-resolve the source and
run `clone_ds.py --drift`. On drift, say the hand-off's tokens may lag the live DS — then continue.
They may be shipping intentionally.

## 1b · Security gate (fail-closed — every mode, before anything is delivered)
A hand-off sends the registry, its render bodies and its mock data off this machine; this is the one place
`security_scan.py` runs for that. Findings are printed already masked.
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/security_scan.py" registry.json
```
Modes 1 and 4 also scan what was written, once the output folder exists (it skips `prototype.html`,
`design-system.html`, any `pb/`, `.git/` and `node_modules/`, so a vendored plugin is not scanned):
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/security_scan.py" --dir handoff        # mode 1 (or --out)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/security_scan.py" --dir handoff/tickets # mode 4
```
- **Exit 2 (errors) → STOP.** Show the findings and ask the user whether to continue. Continue only on
  `--accept-findings` or the user's explicit yes in this conversation; silence is not a yes. Then record the
  override: print it in the Report (the finding codes and counts, and who accepted), and in mode 1 write
  a `## Security scan override` section into the hand-off's own `AGENTS.md`.
- **Exit 1 (warnings only) → continue.** Show the count and say the prototype may contain mock personal data
  (emails, phone numbers) that the recipient will see.
- **Exit 0 → continue**, silently.
- Mode 4 scans `handoff/tickets` before anything is published; a finding in a ticket body or its
  evidence images stops the publish, since a published page leaves the machine.
- Mode 3 scans the registry only, before G-FP1 writes anything; nothing is folder-scanned there.

---

# Mode 1 · Everything, including Product Builder

```
handoff/
  prototype.html            # view-only, self-documenting — opens in any browser
  AGENTS.md                 # orients the recipient (person or a fresh agent session)
  bundle/                   # portable source of truth — /pb:init --import handoff/bundle
    registry.json           #   schema-stamped, so --import can detect an older schema
    render/                 #   the body files — REQUIRED, or every renderSrc dangles
    spec/ logic/ runtime/   #   the sidecar trees, each required once the registry points at one
    design-system/
    memory/constitution.md
    memory/decisions*.md    #   the log AND its rotated siblings
    memory/research/        #   when it exists: instruments and evidence, the proof behind the insights;
                            #   recordings left out unless --with-recordings; HANDOFF.md lists what was withheld
  pb/                       # a copy of ${CLAUDE_PLUGIN_ROOT}
  .claude-plugin/
    marketplace.json        #   rewritten to point at ./pb
```

`--people` writes only the viewer artifact; `--context` only the bundle. Both still emit `AGENTS.md`.

### 1.1 · The view-only prototype
1. Set `config.viewOnly = true` and `config.cover = { title, summary, date, by }` (from `meta.name` +
   `meta.overview.objectives`), then `--render` again.
2. On `config.viewOnly` the shell hides **every** authoring CTA — Push-to-Figma, build controls, sync
   bars, empty-state actions — and shows the cover. The role switcher and Reset stay visible: they are
   how a viewer explores, not how an author edits.
3. Write it to `handoff/prototype.html`.

### 1.2 · The portable bundle
Copy the tree above, preserving the shape `/pb:init --import` expects. **The `decisions*.md` glob is
load-bearing** — rotation moves older entries to dated siblings, so a bare `decisions.md` ships a
hand-off whose history stops at the last rotation, silently. **`memory/research/` holds what participants
said.** Never copy it by hand. After `registry.json` is in the bundle, run:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/research.py" bundle --out handoff/bundle [--with-recordings]
```
It refuses if the bundle has no `registry.json`. It copies `memory/research/` into
`<out>/memory/research/` and leaves out every video file (`.webm` `.mp4` `.mov` `.mkv`) unless
`--with-recordings` is given. It always leaves out `.incoming/` temp folders and symlinks. In the bundle's
copy of the registry it marks each left-out recording row, and each pilot whose media were left out, with
`withheld: {at, reason}`, and it writes `<out>/memory/research/HANDOFF.md`: what was carried and what was
left out (path, bytes, sha256), and how to put one back. It never writes to the source project, replaces
its own earlier output, and refuses a foreign existing folder. Session event files (`kind: session`:
clicks, screens, no typed text) and transcripts are still carried.

**Ask before `--with-recordings`.** A recording is a face and a voice. Use the flag only when the user
confirms the recipient is covered by the participants' consent; otherwise leave it off. Tell the user that
`memory/research/` is in the folder, and how many recordings were left out or included, before it goes
anywhere. `--people` leaves `memory/research/` behind with the rest of the bundle. Mode 1 is the only mode
that carries research evidence; modes 3 and 4 carry none.

### 1.3 · Vendor the plugin
Copy `${CLAUDE_PLUGIN_ROOT}` to `handoff/pb/`, **excluding** `.venv/`, `__pycache__/`, `node_modules/`,
`.reference/` and `fixtures/` — dev weight the recipient does not need. Rewrite `marketplace.json`'s
source path to `./pb`.

> **Why vendor rather than link.** A hand-off that depends on the recipient finding and installing the
> right plugin version stops working the moment either moves. The folder is self-contained or it is not
> a hand-off. Say the added size out loud when you report — it roughly doubles the folder.

### 1.4 · The recipient AGENTS.md
Render `${CLAUDE_PLUGIN_ROOT}/template/AGENTS.template.md` to `handoff/AGENTS.md`, filling
`{{PROJECT_NAME}}` ← `meta.name`, `{{SUMMARY}}` ← the first line of `meta.overview.objectives`,
`{{DATE}}` ← `date +%Y-%m-%d`, `{{SCHEMA_VERSION}}` ← `meta.schemaVersion`, `{{MODE}}` ←
`full` / `people` / `context`. Append: the plugin travels with the folder, the exact install line, and
that `/pb:init --import bundle` is the first command to run.

### 1.5 · Scan the folder
Run the `--dir` scan from §1b on `handoff/` now that it is complete, and apply its exit-code rule.

---

# Mode 2 · retired

Mode 2 (engineering) was removed in v3.0.0; its number is not reused. See **Retired** at the end of this
file for what replaces it.

---

# Mode 3 · For Figma

Reads `registry.json` (`components[]` / `screens[]`) — the same composition tree the prototype renders
from — plus the DS **catalog** (`design-system/<name>/ds-catalog.json`, the DS Bridge *Scan DS*
output cloned by `/pb:pull-ds`). **DS-neutral:** the library comes from the Design System Lock, mirrored
in `figma-transfer.json.dsMatch.library`. One-way, always.

`registry_to_figma.py` does the lowering either way — deterministically, at ~0 model tokens. It is the
source of truth for what gets written. The only choice is who writes it.

> **State the trade-off once, before writing.** Default here is the **MCP**: pb drives the writes and you
> get a built file. That costs model tokens proportional to the node count, needs the connection to hold
> for the whole push, and is the one path where a partial failure leaves a half-built file. `--bridge`
> instead emits node JSON you paste into the plugin — deterministic, offline, and it rebuilds real
> **linked INSTANCES**. If the MCP is unavailable or the push fails partway, **fall back to `--bridge`**,
> emit the JSON, and say exactly which frames landed first.

### G-FP0 · Scope
If `--scope` is absent, ask (1 components · 2 screens · 3 both). Save to `figma-transfer.json.lastScope`.

### G-FP1 · Pre-flight integrity (always)
Sequential; any failure is a HARD FAIL with the exact message and nothing emitted.
1. **DS catalog present** — `design-system/<name>/ds-catalog.json`. Absent → `No DS catalog. Run /pb:pull-ds (with the DS Bridge Scan DS output) first.` *(MCP mode also checks the MCP is reachable — call `whoami`.)*
2. **Registry loaded** — parses, has `components[]` / `screens[]`. Empty → `registry.json has no components/screens. Run /pb:build first.`
3. **`figma-transfer.json` exists or seed it** from `figma-transfer.template.json`; set `dsMatch.library` to the DS Lock name.
4. **No-op detection** — SHA-256 the in-scope slice; equal to `lastPushedHash[<scope>]` and no `--force` → STOP (`✓ No changes since last push.`).
5. **MCP mode only** — resolve the target file / page / root frame. (The bridge builds on the plugin's current page, so it needs no target.)

### G-FP2 · Identity audit (per scope)
- **components / both** — each component with a `dsKey` in `figma-transfer.json` is `bound` (a reference); the rest are `unmatched` and go to G-FP4. A component that maps to a DS key is a **reference**, never a local build.
- **screens / both** — always root frames of INSTANCEs.
- **Affected-screen analysis** — for each changed component, list the screens referencing it (`screens[].elements[].orgId`), so the blast radius is explicit.

Print the audit (bound / unmatched / local counts + ids + affected screens) and ask `Proceed to G-FP3? (yes / cancel)`.
**Batch guard:** in-scope screens > 1 OR components > 5 without `--batch` → HARD FAIL.

### G-FP3 · Token resolution (always)
Collect every token reference in scope — the **union** of component `anatomy.parts[].token.name` +
`spec.stack[]`, screen `elements[].tokens[]`, and every `var(--name)` in the in-scope render bodies.
Resolve each against, in order: `figma-tokens.json`, the ds-catalog `variables[]` by name, then an MCP
`search_design_system` / `get_variable_defs` proposal (context only). Pause:
```
⏸ TOKEN MAPPING NEEDED
  brand         → {DS} Colors/brand   (var_brand)    [catalog]
  space-4       → {DS} Spacing/4      (var_space_4)  [catalog]
  custom-orange → NO MATCH                           [gap — stays numeric + flagged]
Accept all?  (yes / edit / cancel)
```
On `yes` save to `figma-tokens.json`. A no-match is a **gap**, never coerced: numeric fallback + a
`<prop>Token` sidecar, logged to `gaps.md`.

### G-FP4 · DS component match (components or both)
For each `unmatched` component resolve its publish key from `figma-transfer.components[<id>].dsKey`, then
the ds-catalog `components[]` by `dsMatch.component` / name / id, then an MCP proposal (context only). Pause:
```
⏸ DS COMPONENT MATCH   (library: {DS})
  text-input   → {DS} Input   (key 10:200)  [catalog]
  button       → {DS} Button  (key 10:100)  [catalog]
  alert-banner → NO MATCH                   [local build from anatomy]
Accept all?  (yes / edit / cancel)
```
On `yes` save `dsKey` + `propertyMapping`. NO-MATCH → a **local FRAME from anatomy**, its `orgId` parts
nested as INSTANCEs, plus a gap. **Never invent a key.**

### G-FP5 · Plan + confirmation
Print the full plan: scope · library · components (reference-by-key / local-build) · screens · tokens
(bound / gap) · the auto-layout policy (R3: every frame auto-layout). Ask
`Proceed to write? (yes / no / show-detail)`. `--dry-run` → print and STOP.

### Step 6 · Lower, then write
Load the **`figma-use`** skill for the authoring rules, then lower:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/registry_to_figma.py" registry.json \
  --scope <scope> [--screen <id>|--component <id>] \
  --catalog design-system/<name>/ds-catalog.json \
  --tokens figma-tokens.json --transfer figma-transfer.json \
  --out figma-nodes.json --gaps gaps.md
```
It emits `{ meta, roots[], gaps[] }`: each screen → a root FRAME (auto-layout from `layout`) of element
**INSTANCEs** (by DS key + `componentProperties` from the element's props/state); each local component →
a FRAME with its anatomy parts nested as INSTANCEs; spacing → numeric + a `<prop>Token` sidecar.

- **MCP (default)** — write it in, page by page, in order: tokens → components → screens → bindings.
  Then **re-read what landed** (`get_metadata` / `get_screenshot`) and report created-vs-planned.
- **`--bridge`** — hand over the exact steps: open the DS Bridge plugin → **Code → Figma** →
  paste `figma-nodes.json` → **Build / Run**.

Report the gap list plainly either way.

### G-FP6 · Render audit
**Offline (mandatory, before any write — deterministic, machine-checkable on the emitted JSON):**

| # | Invariant |
|---|---|
| 1 | **Auto-layout everywhere** — every FRAME has `layout.mode ≠ NONE` |
| 2 | **Zero absolute children** — no node uses absolute positioning |
| 4 | **Variants as component props** — each INSTANCE's `componentProperties` match the DS component's declared axes |
| 5 | **Screens = instances** — every screen element is an `INSTANCE` with a `component.key`, never inlined markup |
| 7 | **Nested globals = instances** — every local component's `anatomy.parts[]` with an `orgId` is a nested `INSTANCE` |

`tests/r4_figma_bridge.py` asserts 1/2/4/5/7 on the transformer output. Any failure → do **not** write and
do **not** hand over the JSON; fix the registry/mapping and re-emit.

**Round-trip (optional, verifies the built result — invariants 3/5/6):** serialize the built frame back
(plugin *Figma → Code*, or the MCP), diff it against the emitted JSON, and confirm spacing/radius/color
are variable-bound, every element resolved to a real instance, and token coverage. Report the diff.

### Step 7 · Update contracts + log
- **`figma-transfer.json`** — `components[<id>].dsKey` + `propertyMapping`, `nestedInstances`, `lastPushedAt`, `lastPushedHash[<scope>]`, `lastScope`. Portable keys, not file-local node ids.
- **`figma-tokens.json`** — the accepted token → variable `{name,key}` map.
- **`registry.json`** — bridge mode writes back **nothing**. Only the MCP path records `figmaId` / `figmaFrameId`.
- **Push log** — the plan + node count + gaps + contract diff → `memory/figma-pushes/<ISO-timestamp>.log`.

---

# Mode 4 · Tickets for front-end developers

```
handoff/tickets/
  index.md                  # Order | ID | Title | Feature | Depends | Status
  T-<slug>.md               # one ticket per buildable slice, fixed template
  T-<slug>/                 # its evidence: step captures or the annotated screenshot
```

Tickets live **in the project**, one file each. The file is the source; Notion or Jira holds a published
copy. Publishing is one-way, and it refuses to overwrite edits made on the other side (4.6).

`tools/ticket.py` owns the template, the ids, the lint and the export; this command decides what to
write into it. Every call is `python3 "${CLAUDE_PLUGIN_ROOT}/tools/ticket.py" <cmd> [--project DIR]`
(abbreviated `ticket.py` below).

**The template.** Sections, in order: Context · Scope · Solution · States · Edge cases · Roles · Data &
logic · Accessibility · Acceptance · Open · Document · Handoff notes. Required: Context, Scope, Solution,
States, Edge cases, Acceptance, Open, Document — and Roles when the product has more than one role.
**Solution** takes one of four shapes, chosen by `--kind`:

| `--kind` | Solution reads as |
|---|---|
| `journey` | entry → step 1…n → commit → result |
| `component` | anatomy and variants → a trigger table |
| `rules` | ordered checks, each with its exact refusal copy |
| `region` | the UI regions, top to bottom |

**Writing rules.** One checkable rule per bullet. Every UI string appears verbatim in code formatting,
disabled reasons included. Visual values are named by token, never as a raw value. **No pb-internal
references** — no decision ids, lint codes or file paths: the recipient cannot see them.

**Document** is a prototype deep link that opens the exact state, plus exactly **one** evidence form:
`flow` (a step capture of the running prototype, one check per step) or `annotation` (an annotated
screenshot plus a numbered `# | Part | Spec` table inside the ticket).

### 4.1 · Plan the ticket set
Read the registry — `ia.jobs[]`, `screens[]`, `components[]`, `ia.rules[]` and the `flow` scenarios — and
cut **one ticket per buildable slice**. Behaviour shared by several slices (toasts, dialogs, status
labels) gets its own ticket that the others depend on. Present the list, one row per ticket:

```
ID · title · kind · screens · depends · order
T-saved-card-pay  · [Checkout] Pay with a saved card · journey · checkout, receipt · T-toast · 2
```

**Blocking gate: wait for approval.** The user may merge, split, reorder or drop rows. Silence is not
approval. Nothing is written before it.

### 4.2 · Create the skeletons
Per approved ticket:
```
ticket.py new T-<slug> --title "<title>" --feature "<feature>" --kind journey|component|rules|region \
  [--screen <id>]... [--component <id>]... [--rule <id>]... [--scenario <id>]... \
  [--depends T-<slug>]... [--order N] [--base-url URL] [--evidence flow|annotation] [--force]
```
It writes the skeleton with the facts prefilled — the States table, an edge-case row per rule, the role
matrix, acceptance items from the scenarios, the prototype link, the evidence stub and the source digest —
and leaves `<!-- fill -->` where prose goes. `--force` overwrites an existing skeleton; use it only on a
ticket you have not yet filled. `--ticket <ID>` limits this and every later step to that one ticket.

### 4.3 · Fill the prose
Fill every `<!-- fill -->` **from the registry and the logic contract** (`logic/**`, the render bodies,
`content`) — never from `memory/decisions*.md` or other prose alone, which drifts from what is built. Quote
UI strings from `content` and the render bodies, character for character. Every State row and every Edge
case is either filled or says `None` — never left blank. Keep to the writing rules above.

### 4.4 · Evidence
Per ticket, the one form it chose, filed under `handoff/tickets/<ID>/`:
- **`flow`** — capture the running prototype with `tools/shot.py`, one `--step …` per step ending in
  `shot:NAME`, so each step has its own image and one check beside it.
- **`annotation`** — one screenshot with numbered markers, and the `# | Part | Spec` table inside the
  ticket, every marker accounted for.

### 4.5 · Lint, then index
```
ticket.py lint [ID...] [--strict]
ticket.py index
```
`lint` must exit **0** (1 = findings, 2 = usage). Fix findings in the ticket file and re-run.
**`TK-LOGIC`** — a referenced item's logic sidecar is missing — is fixed at the source with `/pb:build`
(regenerate the contract), then re-run; never hand off around it. `TK-STALE` is a warning: re-check the
ticket against the registry, then `ticket.py refresh <ID>` re-stamps its digest. Once lint is clean,
`index` writes `handoff/tickets/index.md`, and the §1b ticket scan runs.

### 4.6 · Publish (one-way)
Ask for the target if `--publish` is absent (Notion · Jira · none). `none` stops after 4.5. For each
ticket, in `order`:
1. **Existing page?** `ticket.py published <ID>` and the publish ledger (what `mark-published` records: target, url, digest, time `at`) say whether it was published before. If
   so, **fetch the page first**. If it was edited after the ledger's `at`, or `published` exits 1 and the
   user did not ask to overwrite, **STOP and ask**: pull those edits into the ticket file, or overwrite
   them. Never pick for the user.
2. `ticket.py export <ID> --format notion` → JSON `{properties, content}`. It refuses a ticket with lint
   errors. For Jira, `--format md` supplies the description.
3. Create or update the page or issue through the Notion MCP (or the Jira MCP).
4. `ticket.py mark-published <ID> --target notion|jira --url <URL>` records the url and the digest.

**The ticket file is the source.** Do not edit a ticket in Notion or Jira as the place the work lives; a
change made there comes back through the ticket file (the pull option in step 1) or is overwritten on
the next publish.

### 4.7 · Re-run later
```
ticket.py stale [ID...]
```
lists the tickets whose registry sources changed since they were cut (exit 1 if any). Update and
re-publish **only those**: re-read the changed sources, edit the prose, `refresh`, lint, then 4.6. A
ticket that is no longer needed leaves a gap in the numbering: the remaining ids are never renumbered,
and a dropped id is never reused.

---

## Report
State the mode, the output path, the file count and the total size, and the security scan result
(clean, N warnings, or the accepted override and its codes). Mode 1: say the plugin is vendored
and what it added, and how many research recordings were left out or included (`--with-recordings`). Mode 3: say which frames were created
and whether anything fell back to the bridge. Mode 4: say how many tickets were written, the lint
result, how many were published (and where) and how many are stale.

## NEVER
- NEVER hand off a stale render — `--render` first, every mode.
- NEVER hand off a registry with an `ERROR` finding (NS6, fail-closed).
- NEVER deliver past a `security_scan.py` exit 2 without `--accept-findings` or the user's explicit yes,
  and never without recording that override in the output.
- NEVER ship a mode-1 `prototype.html` with authoring CTAs visible — set `config.viewOnly`.
- NEVER omit `constitution.md` / `decisions*.md` from a mode-1 bundle, and **never narrow that glob to
  `decisions.md`** — rotated siblings vanish from every hand-off, silently.
- NEVER run the retired engineering hand-off (`--mode=2` / `dev`, `--tier`) or recreate it under another
  name — print the **Retired** note instead.
- NEVER invent a DS publish key or a variable — an unmatched component or token is a **gap**, never a
  fabricated reference; and never coerce a token to a raw value.
- NEVER auto-add a variant axis, push > 1 screen or 5 components without `--batch`, or hardcode a
  design-system name.
- NEVER emit a non-auto-layout frame or an absolutely-positioned child (R3), and never redraw a nested
  global as a local frame.
- NEVER write to Figma while an offline G-FP6 invariant fails, and never attempt bi-directional sync.
- NEVER renumber or reuse a ticket id — deleting a ticket leaves its id taken.
- NEVER publish a ticket that fails lint.
- NEVER overwrite edits made in Notion or Jira without asking, and never treat the published page as the
  source — the ticket file is.
- NEVER cite pb-internal ids or paths (decision ids, lint codes, file paths) in a ticket body.
- NEVER write a ticket's prose from memory files alone — read the registry and the logic contract.
- NEVER hand-edit anything under the output folder — regenerate by re-running `/pb:handoff`.

> **Skill degrade (NS6).** If a step's tool, skill or template fails to load, say so explicitly and
> proceed with its core intent — never silently skip it.

## Retired (v3.0.0)

Mode 2, **For engineering**, is removed completely, along with everything that served it: `--mode=2` /
`dev`, `--tier=host|scaffold|hardened`, the `handoff-dev/` folder, `logic.md` and `rules.md`
(`tools/handoff_docs.py`), the React + Tailwind scaffold (`tools/render_react.py`) and the skill that
described it. `/pb:validate`, already retired, pointed at `--tier=host` and now has no
replacement. Mode numbers were not renumbered, so Figma stays `--mode=3`.

When a run asks for any of it, say this and re-ask §0:

- **Developers** who build the front end → `--mode=4`, tickets: one file per buildable slice, linted,
  published one-way to Notion or Jira.
- **A full working copy** of the project → `--mode=1`, which carries the prototype, the bundle and a
  vendored Product Builder.

`design-system.html` is still rendered by `/pb:build` and served by `/pb:preview` at `/design-system`;
it is no longer a hand-off artifact on its own. `meta.outputTier` and `meta.exportTarget` are inert: an
existing registry keeps them harmlessly, and nothing reads or writes them.
