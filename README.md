# Spec Kit Prototype Builder — Extension

A spec-driven workflow for single-file HTML UX-test prototypes with built-in 5-tab documentation and inline drift detection.

**This repo bundles both halves in one place** (since v0.2.0):

- **Preset** (`preset.yml`) — 4 template overrides + 2 command overrides
- **Extension** (`extension.yml`) — 8 custom commands + 4 lifecycle hooks + the `template.html` asset

You still install them as two SpecKit calls (SpecKit treats Preset and Extension as separate concepts), but there's only **one URL** to remember and one source tree to maintain.

> 📦 The standalone [`spec-kit-preset-prototype-builder`](https://github.com/danhnbui/spec-kit-preset-prototype-builder) repo is now **deprecated** — its contents live here. Existing v0.1.0 installs continue working, but new installs should point here.

---

## What this repo provides

### From the Preset half

| Template override | What it shapes |
|---|---|
| `constitution-template.md` | Adds Principles · Stack Lock · DS Lock · Skill Pinning sections |
| `spec-template.md` | Prototype-shaped user stories with JTBD + Tabs affected + Custom Organisms |
| `plan-template.md` | Adds Tabs Affected + Skills Invoked + Constitution Check sections |
| `tasks-template.md` | Groups tasks by tab + bakes sync rules in |

| Command override | What it changes |
|---|---|
| `/speckit-constitution` | Captures principles + stack lock + DS lock + skill pinning |
| `/speckit-clarify` | Captures User Insights + UI Logic Trade-offs (drives Tab 2 sub-sections) |

### From the Extension half

| Command | Writes to | Trigger |
|---|---|---|
| `/speckit-prototype-builder-scaffold` | `./prototype/template.html`, `./.claude/skills/`, `./design-system/`, locks in `constitution.md` | Run once at project init |
| `/speckit-prototype-builder-build` | Tab 1 (Prototype) + Tab 4-Component | Manual; inline drift check fires first |
| `/speckit-prototype-builder-sync-flow` | Tab 3 (User Flow) | Manual; never auto-triggers |
| `/speckit-prototype-builder-sync-erd` | Tab 5 (ERD) | Manual; never auto-triggers |
| `/speckit-prototype-builder-handoff` | Tab 4-Screen (7:3 split, spec tokens only) | Manual; inline drift check fires first |
| `/speckit-prototype-builder-skills-refresh` | `./.claude/skills/`, constitution.md pinned tag | Manual; opt-in |
| `/speckit-prototype-builder-check-drift` | Drift report only (no writes) | Manual; audit after marathon sessions |
| `/speckit-prototype-builder-sync-tab2` | Tab 2 of `template.html` | Auto-invoked by `after_*` hooks |

### Lifecycle hooks

The Extension registers `after_*` hooks for core SpecKit events to keep Tab 2 in sync:

- `after_constitution` → re-render Tab 2 Principles
- `after_specify` → re-render Tab 2 Overview > Objectives
- `after_clarify` → re-render Tab 2 User Insights + UI Logic Trade-offs
- `after_plan` → optional drift audit prompt

---

## Install (one URL, two commands)

```bash
# Install spec-kit (once per machine)
brew install gh uv
gh auth login
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.8.11

# Per new prototype project:
mkdir ~/Desktop/my-prototype && cd ~/Desktop/my-prototype
specify init . --integration claude --force

# Install Preset + Extension from this single repo
gh repo clone danhnbui/spec-kit-extension-prototype-builder /tmp/pb -- --branch v0.3.16
specify preset add --dev /tmp/pb
specify extension add --dev /tmp/pb

# Or via public URL once the repo is public:
# specify preset add --from https://github.com/danhnbui/spec-kit-extension-prototype-builder/archive/refs/tags/v0.3.16.zip
# specify extension add --from https://github.com/danhnbui/spec-kit-extension-prototype-builder/archive/refs/tags/v0.3.16.zip

# Then open Claude Code and run the workflow
claude
# /speckit-prototype-builder-scaffold
# /speckit-constitution
# /speckit-specify Build a login screen with email + password, error states, success redirect
# /speckit-clarify
# /speckit-plan
# /speckit-tasks
# /speckit-prototype-builder-build
# /speckit-prototype-builder-sync-flow
# /speckit-prototype-builder-handoff
# /speckit-prototype-builder-sync-erd
```

---

## Drift detection

Drift detection is **inline in `/build` and `/handoff` command bodies**, not a SpecKit `before_*` hook. SpecKit's hook system only fires on core lifecycle events; custom commands don't have lifecycle hooks.

**Trio scope**: drift fires only on prompts touching Tab 1, Tab 2, or Tab 4-Component. Decoupled tabs (3, 4-Screen, 5) skip the check.

**Check procedure**: load `constitution.md` Principles → for each, ask if the proposed write contradicts it → if yes, pause-and-ask with the violation surfaced → wait for explicit `yes` / `no` / `revise`.

See [`docs/04-orchestrator.md`](docs/04-orchestrator.md) §3 for the full algorithm.

---

## Architecture

Two halves in one repo, plus the external skill repo:

- **Spec Kit core** provides the workflow shell (`/speckit-constitution`, `/speckit-specify`, etc.)
- **This repo's Preset half** reshapes the artifacts those core commands produce
- **This repo's Extension half** adds 8 new custom commands + 4 `after_*` hooks
- **The [agent-skill-set](https://github.com/danhnbui/agent-skill-set) repo** is cloned at scaffold time into `./.claude/skills/` and supplies the design + critique skills (`think-layout`, `design-component-build`, `design-critics`, `agent-orchestrate-tasks`, etc.)

Full architectural docs (SRS, architecture, data flow, orchestrator, execution plan, handoff brief) are in [`docs/`](docs/).

---

## Requires

- Spec Kit ≥ 0.8.0
- AI agent integration that supports custom slash commands (Claude Code recommended)
- [agent-skill-set](https://github.com/danhnbui/agent-skill-set) repo accessible at v0.2.0 or later (cloned during scaffold)
- `gh` CLI authenticated (since both this repo and `agent-skill-set` are private)

---

## Version

- **v0.3.16** — Fixed the Tab 2 + Tab 4-Component **automation**. Both auto-syncs silently produced empty tabs because the command bodies were design docs, not executable specs: (1) `commands/build.md` §"Tab 4-Component" only built *custom* organisms and told the agent to "list but not rebuild" standard components — so a spec with only standard components (input / button / alert) got an empty Component view by design; it also never named `PB_DATA.handoff.organisms` as the write target. (2) `commands/sync-tab2.md` Step 3 said "find the PB_DATA block (around line 530), replace the keys" — a stale line number, no Edit anchors, no verification. Both are now rewritten as concrete recipes: build.md covers **every** component (standard + custom) with the full `{id,name,renderFn,meta,variants,specs}` organism shape; sync-tab2.md gives an exact Edit-tool recipe with inline target shapes + a Step 3.5 verification pass. The `after_*` hook wiring was already correct — the bug was downstream in the commands they invoke.

- **v0.3.15** — Wireflow nodes upgraded from bare colored rectangles to **real card UI** that matches FigJam-style wireflow references: white card · header bar with screen name · color-coded status badge (`DONE` / `IN PROGRESS` / `NEW` / `ATTENTION` / `ASAP` / `REVIEW` / `PAUSE`) · stylized mini-mockup of the screen inside the body (form-1/2/3 input stacks + CTA, OTP 6-cell row, success checkmark, block exclamation). `WIREFLOW_SCREENS` entries now carry `status` + `preview` fields. New helpers `wfMiniPreview()` + `wfCardHtml()` build the inline HTML; `buildWireflowMermaid()` assembles the Mermaid source so labels render the cards via Mermaid's `htmlLabels` (foreign objects). Width/height set inline on the outer div so Mermaid measures the foreignObject correctly before the stylesheet applies. All other v0.3.14 wiring (click-to-preview, numbered amber note badges, sidebar Flow notes panel) keeps working unchanged.

- **v0.3.14** — Tab 3 becomes a true **wireflow**: each screen-shaped node is labeled with the exact screen name from Tab 4 (Sign in Page, Register Page, Reset Password Page, OTP Verify Page, Home, Contact Support) so reviewers can request edits unambiguously by name. Three new pieces glue it together: (1) `WIREFLOW_SCREENS` registry maps Mermaid node ids to screen renderer functions so **clicking a screen-name node opens a popover preview** of the actual mockup from Tab 4 — no need to tab-switch. (2) `WIREFLOW_NOTES` registry binds **numbered amber badges** on nodes to a "Flow notes" `<ol class="flow-doc-notes">` in the sidebar — for business-logic detail that doesn't fit in an edge label (rate limits, OTP expiry, lockout copy, no-enumeration policy, etc.). (3) New §0.8 platform rule, new docs in `commands/sync-flow.md`, plus CSS + helpers (`openScreenPreviewPopover`, `decorateWireflowNodes`) shipped in `assets/template.html` so a fresh scaffold gets the wireflow surface out-of-the-box once sync-flow populates the registries.

- **v0.3.13** — Auto-positioned hit overlays for Tab 4-Screen Design Handoff. Hand-coded `bounds: 'top:…px;left:…px;…'` strings were brittle (mis-aligned when screen widths changed). New approach: render functions tag each interactive element with `data-handoff-el="<id>"` matching the element's `id` in `PB_DATA.handoff.screens[N].elements`; a new `recomputeHandoffBounds()` helper runs after every `renderHandoff()` and sizes each click-overlay hit to the rendered element's actual bounding rect. Also fires on window resize. Hand-coded `bounds` still work as a fallback. Updated `assets/template.html` (helper + patched `renderHandoff`) and `commands/handoff.md` (Step 3 documents the new convention).

- **v0.3.12** — 24px corner radius on rectangle-shaped nodes (Action + Subprocess). Two changes: (1) subprocess syntax in the canonical Mermaid template switches from `R[[Subprocess]]` (renders as stadium-bordered polygon, can't be rounded) to `R(Subprocess)` (renders as rect, accepts `rx/ry`). (2) Post-render JS in the host template's `renderMetaFlow()` sets `rx="24" ry="24"` on every `.node.cAction > rect` and `.node.cSubprocess > rect` because Mermaid's `classDef rx/ry` isn't honored on rectangles in the current renderer. Stadiums (Start/End) keep their fully-rounded pill ends; polygons (Decision/Input) can't be rounded.

- **v0.3.11** — Updates platform rule §0.7: connectors are now **orthogonal (horizontal/vertical only)** with right-angle bends — switches Mermaid from `flowchart: { curve: 'basis' }` (smooth curves) to `flowchart: { curve: 'step' }`. No diagonals, no smooth curves; matches the whiteboard-flowchart convention and reads cleaner on a stacked canvas. Pure config tweak — no other behavior changes.

- **v0.3.10** — Refines platform rule §0.4 after user feedback: prefer **one combined flow** that covers the whole prototype (including edge cases), with per-story detail pushed into `[[Subprocess]]` nodes and the test checklist on the left mapping each story to a path. Only stack multiple flow sections when the flows are truly independent OR when a single combined flow would exceed 9 nodes after subprocess extraction. Claude ASKS when unsure. The v0.3.9 zoomable canvas, curved connectors, and color palette remain — this is purely a defaulting change. The reference test project (`test-pb-signin`) now ships a single 8-node combined flow that traces all 5 user stories (sign in / register / forgot password happy / forgot password throttled / sign-in lockout).

- **v0.3.9** — Reverses two v0.3.8 rules after user feedback: User Flow now covers **ALL flows** for the prototype (not just one) inside a **zoomable canvas** (pan + scroll-to-zoom + fit-to-view, via the existing `.flow-canvas` / `.flow-viewport` / `.flow-stage` trio shared with ERD). Connectors switch from straight lines to **curved** (`flowchart: { curve: 'basis' }`) for the FigJam-style aesthetic. Color palette refreshed: Start/End are **zinc-900 pills** (was emerald/zinc), Action is **lavender** (was blue), Decision is **sky** (was amber) — matches the visual reference. Each flow gets its own `<div class="flow-doc-section">` inside `#flow-stage`; sync-flow stacks them vertically and hands off to `initCanvas('flow', W, H)` after measuring natural content size. Platform rule 4 now reads "cover ALL flows in a zoomable canvas, each individual flow still observes the 5–9 node limit"; rule 6 has the new palette; rule 7 says curved connectors.

- **v0.3.8** — User Flow tab gets a real authoring surface: **7 new platform rules** that override the legacy multi-flow default. Layout is now a **3:7 grid** — test checklist on the LEFT, Mermaid flowchart canvas on the RIGHT, full panel width. Every prototype produces **one flow** (LR direction, color-coded shapes via `classDef`, straight-line connectors via `flowchart: { curve: 'linear' }`); if the spec is too complex even after extracting `[[Subprocess]]`es, sync-flow ASKS the user how to scope before drawing. Canvas top-right has a **pill-shaped legend** with shape swatches + a `?` button that opens an anchored popover explaining every shape (Start / End / Action / Decision / Input / Subprocess / External system) and connector style. Updated `docs/USER-FLOW-GUIDE.md` (new §0 "Platform rules") and `commands/sync-flow.md` to enforce these, plus `assets/template.html` ships the `.flow-doc-*` CSS, the `openLegendPopover` helper, and the linear-curve Mermaid init.

- **v0.3.7** — Each slash command now ships as **two representations** in the copy popover, each with its own copy button: a `/slash` form for the **Claude Code terminal** AND a short natural-language prompt (e.g. `Run speckit-prototype-builder-sync-flow to generate Tab 3...`) for the **Claude Code chat input**. The chat-input prompt mentions the command name as a keyword that the scaffold-installed routing rule in `./CLAUDE.md` catches — Claude then reads `.specify/extensions/prototype-builder/commands/<name>.md` and executes it. Replaces the v0.3.6 approach of copying command files into `.claude/commands/`, which depended on session restarts and project-context discovery that often failed in practice. Shell commands (e.g. `gh repo clone`) remain single-format (Terminal only).

- **v0.3.6** — Slash commands now work in **both** the Claude Code chat input ("Type / for commands" field in the desktop app / IDE extension) **and** the Claude Code terminal — not just the terminal. Two changes: (1) the scaffold now copies each user-facing command body (`build`, `sync-flow`, `sync-erd`, `handoff`, `skills-refresh`, `check-drift`, `scaffold` itself) into `./.claude/commands/speckit-prototype-builder-<name>.md`, which is the directory Claude Code reads to register chat-input commands. (2) The copy popover now shows BOTH destinations side-by-side under a "Paste in either:" heading — Claude Code chat input (with chat-bubble icon) OR Claude Code terminal (with terminal icon) — so users pick whichever surface they have open. Shell commands (e.g., `gh repo clone`) still show Terminal-only since they can't run in the chat input.

- **v0.3.5** — Sync / Generate CTAs now open a **copy popover** instead of fire-and-forget toasts. The popover shows the command in a code block with a copy-icon button, a "✓ Copied to clipboard" status line, and explicit destination guidance: all slash commands → "Paste in **Terminal** (Claude Code CLI)" with setup instructions ("Open Terminal → type `claude` if not running → paste → ↵"). Auto-copies on open; persists until ×, backdrop click, or Esc. Also removed the redundant meta-footer text that used to sit below each empty-state CTA (the popover covers the same information).

- **v0.3.4** — Removed the "Read the 18 flow rules →" external link from the User Flow empty state. Cleaner CTA-only layout. The guide is still available at [`docs/USER-FLOW-GUIDE.md`](docs/USER-FLOW-GUIDE.md) for anyone who needs it.

- **v0.3.3** — Toast auto-detects destination. `copyAndToast(command, label, btn, dest)` now picks "Claude Code" or "Terminal" automatically: commands starting with `/` are slash commands (Claude Code), everything else is a shell command (Terminal). Override the auto-detection by passing `dest: 'claude'` or `dest: 'terminal'` as the 4th arg. Avoids the confusion of telling users to "paste in Claude Code" when the command is actually `gh repo clone ...` (Terminal).

- **v0.3.2** — Empty states + user-flow guide. Three additions:
  1. **Empty states for Tab 3 (User Flow), Tab 4-Screen (Design Handoff), Tab 5 (ERD)** — when the tab hasn't been synced yet, the placeholder demo is replaced with a clean empty state: heading + body copy + primary CTA button (clicking copies the relevant slash command + flashes ✓ + shows toast). For Tab 3, the empty state also includes a "Read the 18 flow rules →" link to the new guide.
  2. **[`docs/USER-FLOW-GUIDE.md`](docs/USER-FLOW-GUIDE.md)** — compact cheat-sheet distilled from the `design-generate-userflow` skill: 6 standard shapes, 18 enforced rules, output format, validation checklist. The `/speckit-prototype-builder-sync-flow` command now references this guide and must conform to its rules.
  3. **PB_DATA shape extension**: `PB_DATA.flow.populated` and `PB_DATA.erd.populated` flags (default `false`) gate the empty-state vs. populated render. Sync commands set them to `true` after writing real content. Backwards-compatible — pre-v0.3.2 hooks that don't set these flags just keep the tabs in empty state.

- **v0.3.1** — Sync now button feedback. The Sync button now also (a) flashes its label to "✓ Copied" with a green background for 1.5s after click, (b) moves the toast from bottom-center to top-center (just below the meta-nav, in the user's eyeline), (c) extends toast duration from 2.2s → 3s, (d) adds a checkmark icon to the toast, and (e) switches the toast appearance from `requestAnimationFrame` to `setTimeout(10ms)` — fixes a bug where the toast could be invisibly stuck in backgrounded/iframed contexts. No PB_DATA contract changes.
- **v0.3.0** — Template UX iteration (`assets/template.html`). No command body changes. Five additions to the 5-tab template:
  1. **Tab 2 sub-tabs**: Overview / User Insights / UI Logic Trade-offs / Others render as sub-tabs instead of one long scroll
  2. **Full-width** Tab 3 / Tab 4 / Tab 5 panels (Tab 2 stays narrow for readability)
  3. **Legend on LEFT, canvas on RIGHT** for User Flow + ERD (CSS `flex-direction: row-reverse` at viewport ≥1081px)
  4. **Tab 4-Component**: vertical card list with inline variant previews. Click a card → right-side drawer with 5 spec segments (Tokens · Sizing · States · A11y · Usage). Esc / backdrop closes
  5. **"Sync now" buttons** on Tab 3 / Tab 4-Screen / Tab 5 — copies the relevant slash command to clipboard + 2-second toast (replaces the static sync-badge hint)

  **PB_DATA shape extension**: `organisms[N].specs = { tokens, sizing, states, a11y, usage }` is now read by the drawer. Existing v0.2.0 hooks that don't write `specs` still work — the card just shows a "no spec data yet" hint instead of being clickable.

- **v0.2.0** — Folded the Preset into this repo (was previously the separate [`spec-kit-preset-prototype-builder`](https://github.com/danhnbui/spec-kit-preset-prototype-builder) repo). One URL, one source of truth, still two install commands per SpecKit convention.
- **v0.1.1** — Skill repo pin bumped to `agent-skill-set@v0.2.0` (the 3 design/orchestration skills landed). No command behavior changes.
- **v0.1.0** — Initial private release for PropertyGuru Vietnam prototype work.
