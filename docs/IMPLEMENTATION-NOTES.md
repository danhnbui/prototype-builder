# Implementation Notes — Deltas from Original Handoff Docs

**Date**: 2026-05-17
**Author**: Claude Code (Opus 4.7, 1M context) on Danh's machine
**Audience**: anyone reading the 6 handoff docs in this folder

The 6 docs in this folder (`HANDOFF.md`, `01-srs.md` through `05-execution-plan.md`, plus `PROTOTYPE-BUILDER.md`) were authored before SpecKit was inspected first-hand. After researching SpecKit v0.8.11's actual Preset/Extension API, the original 2-layer single-repo architecture was found to be incompatible with real SpecKit.

The user (Danh) chose **Path A+ = real SpecKit, inline drift check** to resolve the divergence. This note describes the deltas between what the docs say and what was actually built.

---

## Delta 1 — Repo count: 1 → 3

**Docs assume**: A single per-prototype repo holds the SpecKit Preset, Extension, and the project itself ([02-architecture.md §1, §2](02-architecture.md)).

**Reality**: SpecKit Presets and Extensions are **standalone redistributable packages**, each with its own GitHub repo and manifest, installed via `specify preset add` / `specify extension add`.

**What was built**:

| Repo | Role | Path |
|---|---|---|
| `agent-skill-set` | Skills cloned at scaffold-time | github.com/danhnbui/agent-skill-set (existed empty; staged at /tmp/skill-staging/, awaiting your push) |
| `spec-kit-preset-prototype-builder` | Artifact template + core command overrides | /Users/danhbnp/Desktop/spec-kit-preset-prototype-builder/ |
| `spec-kit-extension-prototype-builder` | 7 custom commands + after_* hooks + template.html asset | /Users/danhbnp/Desktop/spec-kit-extension-prototype-builder/ |

The **per-prototype project** is whatever directory the user runs `specify init` in — it ends up with `.specify/`, `.claude/`, `./design-system/`, `./prototype/template.html`.

---

## Delta 2 — Manifest filenames

**Docs assume**: `.specify/presets.yml` and `.specify/extensions.yml` in the target project ([02-architecture.md §2, §4, §5](02-architecture.md)).

**Reality**: SpecKit uses `preset.yml` and `extension.yml` (singular), each living in **its own repo's root**, not in the target project's `.specify/`.

---

## Delta 3 — Drift-check hooks: removed

**Docs assume**: `before_build: check_drift_trio` and `before_handoff: check_drift_trio` as Extension manifest hooks ([02-architecture.md §5](02-architecture.md), [04-orchestrator.md §3](04-orchestrator.md)).

**Reality**: SpecKit hooks only fire on **core lifecycle events**: `before_constitution`/`after_constitution`, `before_specify`/`after_specify`, `before_clarify`/`after_clarify`, `before_plan`/`after_plan`, `before_tasks`/`after_tasks`, `before_implement`/`after_implement`, `before_analyze`/`after_analyze`, `before_checklist`/`after_checklist`, `before_taskstoissues`/`after_taskstoissues`. Custom commands (`/build`, `/handoff`) **cannot register lifecycle hooks**.

**What was built**: Drift check lives **inline in the command bodies** of `commands/build.md` and `commands/handoff.md`. It's prompt-driven (the AI agent runs the check) rather than deterministic. The pause-and-ask UX shape from [04-orchestrator.md §3.3](04-orchestrator.md) is preserved exactly.

Additionally, the Extension registers four `after_*` hooks that auto-sync Tab 2 of `template.html` when the user runs core SpecKit commands:

- `after_constitution` → Tab 2 → Principles
- `after_specify` → Tab 2 → Overview > Objectives
- `after_clarify` → Tab 2 → User Insights + UI Logic Trade-offs
- `after_plan` → no-op write; hints user to run `/build`

---

## Delta 4 — Custom command names: namespaced

**Docs assume**: bare `/build`, `/sync.flow`, `/handoff`, etc.

**Reality**: SpecKit convention requires extension commands to be namespaced as `speckit.<extension-id>.<command-name>`. So the actual command names are:

| Original | Actual |
|---|---|
| `/build` | `/speckit.prototype-builder.build` |
| `/sync.flow` | `/speckit.prototype-builder.sync-flow` |
| `/sync.erd` | `/speckit.prototype-builder.sync-erd` |
| `/handoff` | `/speckit.prototype-builder.handoff` |
| `/skills.refresh` | `/speckit.prototype-builder.skills-refresh` |
| `/check.drift` | `/speckit.prototype-builder.check-drift` |
| (new) | `/speckit.prototype-builder.scaffold` |

The new `/speckit.prototype-builder.scaffold` command handles the init-time work originally implied by `specify init` itself (clone skill repo, copy `template.html`, prompt for DS + stack, write locks into `constitution.md`).

---

## Delta 5 — Tab 2 sub-sections — fully implemented in template.html

`template.html` (the asset at `assets/template.html`) was modified to:

1. Replace the old 3-section Tab 2 layout (Objective / Principles / Key Logics & Rules) with the 4-sub-section layout from [02-architecture.md §7 Addition C](02-architecture.md):
   - **2.1 Overview** (Objectives from spec.md + Principles from constitution.md)
   - **2.2 User Insights** (Quantitative Data + Research Summary Report + Executive Summary, from clarify.md)
   - **2.3 UI Logic Trade-offs** (from clarify.md)
   - **2.4 Others** (reserved per-project)
2. Replace the old "Component Variants" tab with a **Design Handoff** tab that has a Component/Screen toggle.
3. Add a 7:3 CSS grid for the Screen view per [02-architecture.md §7 Addition B](02-architecture.md). Left panel = screen render + clickable element overlay + logic notes. Right panel = selected element's DS tokens + sizing + state, with a footer reminding the agent that code is forbidden in this panel.
4. Add staleness badges (amber chips) on Tab 3, Tab 4-Screen, Tab 5 in the nav bar; gap is computed from `PB_DATA.staleness`.
5. Add a `PB_DATA` global at the top of the inline `<script>` as the single write target for `/build`, `/handoff`, and the `after_*` hooks. Render functions read from `PB_DATA` and fall back to empty-state copy.

---

## Delta 6 — template.html distribution

**Docs assume**: `template.html` lives in `.specify/` and `specify init` copies it ([02-architecture.md §7](02-architecture.md), [05-execution-plan.md Task 3.1](05-execution-plan.md)).

**Reality**: SpecKit doesn't have a "ship arbitrary asset" primitive. The Extension ships `template.html` at `assets/template.html`; the `/speckit.prototype-builder.scaffold` command copies it from the extension's install directory into the project's `./prototype/template.html`.

---

## Delta 7 — Skill repo: still required, mechanism revised

**FR-5 mechanism**: `git clone --depth 1 --branch <pinned-tag> <url> ./.claude/skills` — now lives in `commands/scaffold.md` Step 2 (not in a separate init script).

**Required-skills check**: 10 required + 1 optional, checked in `commands/scaffold.md` Step 3. Hard-fail messages match FR-5's wording.

**Current status of the skill repo** (as of 2026-05-17):
- `agent-skill-set` exists, is private, is empty.
- 7 of 10 required skills (`think-critique-prd`, `think-clarify`, `ref-blueprint`, `ref-prd`, `think-layout`, `think-logic`, `craft-connect-flow`) + 1 optional (`craft-research`) are staged at `/tmp/skill-staging/agent-skill-set/`, awaiting your push.
- 3 required skills (`design-component-build`, `design-critics`, `agent-orchestrate-tasks`) are accessible via Claude Code's `anthropic-skills:*` plugin namespace; their physical files are at `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/.../skills/`. **Resolution of these 3 is still your decision** — see [05-execution-plan.md Phase 0.3](05-execution-plan.md) options.

---

## Delta 9 — Preset and Extension unified into one repo (v0.2.0)

**Docs assume**: Preset and Extension are two separate repos ([01-srs.md FR-1, FR-2](01-srs.md), [02-architecture.md §1, §2, §4, §5](02-architecture.md)).

**Reality** (as of `spec-kit-extension-prototype-builder@v0.2.0`, 2026-05-17): the Preset's files (`preset.yml`, `templates/`, `commands/speckit.constitution.md`, `commands/speckit.clarify.md`) now live in **this** repo alongside the Extension's files. Reasons:

- SpecKit allows a single folder to contain both a `preset.yml` and an `extension.yml` — the `specify preset add` and `specify extension add` commands each look for their respective manifest file.
- One source of truth, one URL to remember, one place to bump versions.
- The standalone [`spec-kit-preset-prototype-builder`](https://github.com/danhnbui/spec-kit-preset-prototype-builder) repo is **deprecated** but kept read-only for v0.1.0 reference.

**Install flow now**:

```bash
gh repo clone danhnbui/spec-kit-extension-prototype-builder /tmp/pb -- --branch v0.2.0
specify preset add --dev /tmp/pb         # one repo, two install commands
specify extension add --dev /tmp/pb
```

SpecKit still treats Preset and Extension as separate concepts internally (separate manifests, separate priority in template resolution, separate `specify preset|extension` subcommands). Collapsing further would require forking SpecKit, which is forbidden by Hard Rule #6.

---

## Delta 8 — Multi-prototype workspace — still out of scope, but mechanism easier

**Docs assume**: Multi-prototype workspace is a future migration that involves moving `.specify/templates/` and `.specify/extensions/` to a shared location ([02-architecture.md §9](02-architecture.md)).

**Reality**: Because the Preset and Extension are now **already in their own repos**, multi-prototype is already partially solved — every new prototype project just runs `specify preset add prototype-builder && specify extension add prototype-builder` to pull them. No migration of files needed.

---

## What's still aligned with the original docs

- **5-tab template structure** (Prototype · Project Summary · User Flow · Design Handoff · ERD) — preserved
- **Trio vs decoupled tab semantics** — preserved
- **HITL gates G0–G6** — preserved (G0 = skill repo ready, G1 = drift, G2 = DS, G3 = stack, G4 = skill repo unreachable, G5 = per-task, G6 = final)
- **Hard rules from HANDOFF.md** — all preserved verbatim in the new command bodies
- **Drift-check algorithm** ([04-orchestrator.md §3](04-orchestrator.md)) — preserved verbatim, just relocated to inline command bodies
- **Pause-and-ask UX shape** ([04-orchestrator.md §3.3](04-orchestrator.md)) — preserved exactly
- **ERD guardrails** (5 of them, see [01-srs.md FR-3](01-srs.md) and `commands/sync-erd.md` Step 4) — preserved
- **Required skills list** ([04-orchestrator.md §2](04-orchestrator.md)) — preserved

---

## Open items / known gaps

1. **3 plugin-namespaced skills** — your call: extract from `~/Library/.../skills-plugin/`, substitute local equivalents (`build-generate` etc.), or author fresh.
2. **Skill repo push** — auto-mode classifier blocked `git push` of even user-authored skills. The staging area at `/tmp/skill-staging/agent-skill-set/` is ready; you need to push manually.
3. **SpecKit install** — auto-mode classifier blocked `uv tool install`. You need to install manually: `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.8.11`.
4. **Skill repo visibility** — currently private. Recommendation in plan is to keep private + use `gh repo clone` for scaffold, or make public if skills are non-sensitive. Decision not yet made.
5. **`commands/scaffold.md` Step 4 path resolution** — the command says "Resolve the extension's local path via SpecKit's extension manager (`ExtensionRegistry`)" but this hasn't been verified to work end-to-end. The smoke test (Phase 6) will exercise this.
6. **NFR-1 token budget** — drift check is now prompt-driven inline; original estimate of ~40K tokens per 50-turn session ([03-data-flow.md §6](03-data-flow.md)) still applies. Post-Phase-7 optimizations deferred.
7. **End-to-end smoke test (Phase 6)** — blocked on SpecKit install.

---

## File map of what was built

```
~/Desktop/
├── spec-kit-preset-prototype-builder/
│   ├── preset.yml
│   ├── README.md
│   ├── LICENSE
│   ├── templates/
│   │   ├── constitution-template.md   ← Principles + Stack Lock + DS Lock + Skill Pinning
│   │   ├── spec-template.md           ← prototype-shaped user stories
│   │   ├── plan-template.md           ← Tabs Affected + Skills Invoked + Constitution Check
│   │   └── tasks-template.md          ← per-tab task grouping
│   └── commands/
│       ├── speckit.constitution.md    ← override w/ prototype 3-section structure
│       └── speckit.clarify.md         ← override w/ User Insights + UI Logic Trade-offs
│
├── spec-kit-extension-prototype-builder/
│   ├── extension.yml                  ← 7 commands + 4 after_* hooks
│   ├── README.md
│   ├── LICENSE
│   ├── commands/
│   │   ├── scaffold.md                ← init-time: clone skills, copy template.html, prompt for DS+stack
│   │   ├── build.md                   ← Tab 1 + Tab 4-C; inline drift G1, G2, G3
│   │   ├── handoff.md                 ← Tab 4-S; inline drift; spec-tokens-only enforcement
│   │   ├── sync-flow.md               ← Tab 3; never auto-triggers
│   │   ├── sync-erd.md                ← Tab 5; 5 guardrails
│   │   ├── skills-refresh.md          ← refresh w/ rollback
│   │   └── check-drift.md             ← read-only audit
│   ├── assets/
│   │   └── template.html              ← 1444 lines; PB_DATA + 4 sub-sections + dual-view + staleness
│   └── docs/
│       ├── HANDOFF.md                 ← original
│       ├── 01-srs.md                  ← original
│       ├── 02-architecture.md         ← original (see Deltas 1-2 above)
│       ├── 03-data-flow.md            ← original
│       ├── 04-orchestrator.md         ← original (see Delta 3 above)
│       ├── 05-execution-plan.md       ← original (superseded by current plan file)
│       ├── PROTOTYPE-BUILDER.md       ← original author's guide
│       └── IMPLEMENTATION-NOTES.md    ← this file
│
└── (skill repo staging)
    /tmp/skill-staging/agent-skill-set/   ← 7 user-authored skills + README staged; awaiting your push
```
