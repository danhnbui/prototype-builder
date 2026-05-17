# Spec Kit Extension — Prototype Builder

Adds 7 custom slash commands to [Spec Kit](https://github.com/github/spec-kit) for building single-file HTML UX-test prototypes with built-in 5-tab documentation and inline drift detection.

Pair with the companion **[Prototype Builder Preset](https://github.com/danhnbui/spec-kit-preset-prototype-builder)** for prototype-shaped artifact templates.

## What this extension adds

| Command | Writes to | Trigger |
|---|---|---|
| `/speckit.prototype-builder.scaffold` | `./prototype/template.html`, `./.claude/skills/`, `./design-system/`, locks in constitution.md | Manual, run once at project init |
| `/speckit.prototype-builder.build` | Tab 1 (Prototype) + Tab 4-Component | Manual; inline drift check fires first |
| `/speckit.prototype-builder.sync-flow` | Tab 3 (User Flow) | Manual; never auto-triggers |
| `/speckit.prototype-builder.sync-erd` | Tab 5 (ERD) | Manual; never auto-triggers |
| `/speckit.prototype-builder.handoff` | Tab 4-Screen (7:3 split, spec tokens only) | Manual; inline drift check fires first |
| `/speckit.prototype-builder.skills-refresh` | `./.claude/skills/`, constitution.md pinned tag | Manual; opt-in |
| `/speckit.prototype-builder.check-drift` | Drift report only (no template writes) | Manual; audit after marathon sessions |

## Hooks

This extension registers `after_*` hooks for the core SpecKit lifecycle to keep Tab 2 (Project Summary) in sync with constitution.md, spec.md, and clarify.md:

- `after_constitution` → Tab 2 → Principles
- `after_specify` → Tab 2 → Overview > Objectives
- `after_clarify` → Tab 2 → User Insights + UI Logic Trade-offs
- `after_plan` → no auto-write; hints user to run `/build`

## Architecture

The full architectural docs (SRS, architecture, data flow, orchestrator, execution plan, handoff brief) live in [`docs/`](docs/) of this repo.

In one paragraph: **Spec Kit core** provides the workflow shell (`/speckit.constitution`, `/speckit.specify`, etc.). The **Prototype Builder Preset** customizes the artifact templates for prototype work. **This Extension** adds the 6 custom commands and 1 scaffold command. The **[agent-skill-set](https://github.com/danhnbui/agent-skill-set) repo** is cloned at scaffold-time and supplies the design + critique skills (`think-layout`, `design-component-build`, `design-critics`, etc.).

## Install

```bash
# Install spec-kit
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.8.11

# Install the preset (artifact template customizations)
specify preset add --from https://github.com/danhnbui/spec-kit-preset-prototype-builder/archive/refs/tags/v0.1.0.zip

# Install this extension (custom commands)
specify extension add --from https://github.com/danhnbui/spec-kit-extension-prototype-builder/archive/refs/tags/v0.1.0.zip

# Init a new prototype project
specify init my-prototype --integration claude
cd my-prototype
/speckit.prototype-builder.scaffold     # clones skills, copies template.html, prompts for DS + stack
/speckit.constitution                   # uses preset's prototype-shaped template
/speckit.specify Build a login screen with email + password, error states, success redirect
/speckit.clarify                        # captures UI Logic Trade-offs
/speckit.plan
/speckit.tasks
/speckit.prototype-builder.build        # writes Tab 1 + Tab 4-Component
/speckit.prototype-builder.sync-flow    # writes Tab 3
/speckit.prototype-builder.handoff      # writes Tab 4-Screen
/speckit.prototype-builder.sync-erd     # writes Tab 5
```

## Drift detection

Drift detection is **inline in `/build` and `/handoff` command bodies**, not a SpecKit before-hook. (Reason: SpecKit's hook system only fires on core lifecycle events; custom commands don't have lifecycle hooks.)

**Trio scope**: Drift fires only on prompts touching Tab 1, Tab 2, or Tab 4-Component. Decoupled tabs (3, 4-Screen, 5) skip the check.

**Check procedure**: Load `constitution.md` Principles → for each principle, ask if the proposed write contradicts it → if yes, pause-and-ask with the violation surfaced → wait for explicit `yes` / `no` / `revise`.

See [`docs/04-orchestrator.md`](docs/04-orchestrator.md) §3 for the full algorithm.

## Requires

- Spec Kit ≥ 0.8.0
- AI agent integration that supports custom slash commands (Claude Code recommended)
- [agent-skill-set](https://github.com/danhnbui/agent-skill-set) repo accessible (cloned during scaffold)
- [spec-kit-preset-prototype-builder](https://github.com/danhnbui/spec-kit-preset-prototype-builder) installed

## Version

- **v0.1.1** — Skill repo pin bumped to `v0.2.0` (includes the 3 design/orchestration skills). No command behavior changes.
- **v0.1.0** — Initial private release for PropertyGuru Vietnam prototype work.
