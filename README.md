# Spec Kit Prototype Builder — Preset + Extension (unified)

A spec-driven workflow for single-file HTML UX-test prototypes with built-in 5-tab documentation and inline drift detection.

**This repo bundles both halves in one place** (since v0.2.0):

- **Preset** (`preset.yml`) — 4 template overrides + 2 command overrides
- **Extension** (`extension.yml`) — 8 custom commands + 4 lifecycle hooks + the `template.html` asset

You still install them as two SpecKit calls (SpecKit treats Preset and Extension as separate concepts), but there's only **one URL** to remember and one source tree to maintain.

> 📦 The standalone [`spec-kit-preset-prototype-builder`](https://github.com/danhnbui/spec-kit-preset-prototype-builder) repo is now **deprecated** — its contents live here. Existing v0.1.0 installs continue working but new installs should point here.

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
gh repo clone danhnbui/spec-kit-extension-prototype-builder /tmp/pb -- --branch v0.3.0
specify preset add --dev /tmp/pb
specify extension add --dev /tmp/pb

# Or via public URL once the repo is public:
# specify preset add --from https://github.com/danhnbui/spec-kit-extension-prototype-builder/archive/refs/tags/v0.3.0.zip
# specify extension add --from https://github.com/danhnbui/spec-kit-extension-prototype-builder/archive/refs/tags/v0.3.0.zip

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
