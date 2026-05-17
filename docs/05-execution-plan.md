# 05 — Execution Plan

**Purpose**: The actionable task list. Claude Code reads this and executes phase by phase. Every task has inputs, outputs, acceptance criteria, dependencies, and HITL gates.

**How to read this file**: Execute phases in order. Within a phase, tasks can usually run in sequence; any task marked `[P]` can be parallelized with siblings. STOP at every HITL gate.

---

## Phase summary

| Phase | Owner | Description | Blocks next phase? |
|-------|-------|------------|-------------------|
| 0 | **Danh** | Pre-flight skill repo sync (side task) | Yes |
| 1 | Claude Code | SpecKit Preset scaffolding | Yes |
| 2 | Claude Code | SpecKit Extension scaffolding | Yes |
| 3 | Claude Code | Template wiring (SpecKit → template.html) | Yes |
| 4 | Claude Code | Skill clone mechanism | No (can overlap with 5) |
| 5 | Claude Code | Drift detection implementation | Yes |
| 6 | Claude Code | Tab sync rules implementation | Yes |
| 7 | Joint | Acceptance test on real prototype | Final gate |

---

## Phase 0 — Pre-flight (Danh's side task)

**This phase blocks everything.** Claude Code MUST NOT start Phase 1 until Danh confirms Phase 0 is done.

### Task 0.1 — Create the skill repo

- **Inputs**: existing skills at `/mnt/skills/user/*` on Danh's machine
- **Outputs**: `github.com/danhnbui/agent-skill-set` repo, public or private with auth configured
- **Acceptance**: Anyone with the URL can `git clone` it
- **Dependencies**: none
- **HITL gate**: none (Danh's local work)
- **Effort**: 10 min

### Task 0.2 — Push skills to the repo

- **Inputs**: skills from `/mnt/skills/user/*`
- **Outputs**: repo populated with at least the required-skills list from `04-orchestrator.md` section 2
- **Acceptance**: `git clone <url> tmp && ls tmp/think-layout/SKILL.md` returns a file
- **Dependencies**: 0.1
- **Effort**: 20 min

### Task 0.3 — Tag a release

- **Inputs**: pushed skills
- **Outputs**: git tag `v0.1.0` on the repo
- **Acceptance**: `git ls-remote --tags <url>` shows `refs/tags/v0.1.0`
- **Dependencies**: 0.2
- **Effort**: 5 min

### Task 0.4 — Verify clone from clean directory

- **Inputs**: tagged repo
- **Outputs**: confirmation that `git clone --branch v0.1.0 <url>` works from a fresh shell
- **Acceptance**: Clone completes in <30s, all required skills present
- **Dependencies**: 0.3
- **Effort**: 5 min

### 🛑 HITL Gate G0
Danh confirms in chat: **"Skill repo ready"** → Phase 1 unlocked.

---

## Phase 1 — SpecKit Preset scaffolding

Build the Preset that overrides SpecKit's default phase templates.

### Task 1.1 — Create the Preset skeleton

- **Inputs**: SpecKit installed on Danh's machine, `specify` CLI working
- **Outputs**: `.specify/presets.yml` with `name: prototype-builder, version: 1.0.0, priority: 100`
- **Acceptance**: `specify preset list` shows `prototype-builder`
- **Dependencies**: Phase 0 complete
- **HITL gate**: G5 after creation
- **Effort**: 15 min

### Task 1.2 — Override `constitution.md` template

- **Inputs**: SpecKit's default constitution template; prototype principles from `01-srs.md` section 1
- **Outputs**: `.specify/templates/commands/constitution.md`
- **Acceptance**: Running `/speckit.constitution` in a test project emits a constitution shaped for prototypes (sections: Principles, Stack Lock, DS Lock)
- **Dependencies**: 1.1
- **HITL gate**: G5 after Danh reviews emitted constitution
- **Effort**: 30 min

### Task 1.3 — Override `specify.md` template

- **Inputs**: SpecKit default; Tab 2 Overview > Objectives section schema from `02-architecture.md` section 7
- **Outputs**: `.specify/templates/commands/specify.md`
- **Acceptance**: Running `/speckit.specify` emits a spec.md whose Objectives map cleanly to Tab 2 Overview
- **Dependencies**: 1.1
- **HITL gate**: G5
- **Effort**: 25 min

### Task 1.4 — Override `clarify.md` template

- **Inputs**: SpecKit default; Tab 2 sub-section schema (User Insights, UI Logic Trade-offs)
- **Outputs**: `.specify/templates/commands/clarify.md`
- **Acceptance**: Running `/speckit.clarify` emits sections that populate Tab 2 sub-sections
- **Dependencies**: 1.1
- **HITL gate**: G5
- **Effort**: 25 min

### Task 1.5 — Override `plan.md` template

- **Inputs**: SpecKit default; tab-and-skill plan format
- **Outputs**: `.specify/templates/commands/plan.md` that emits a plan citing which tabs are touched and which skills are invoked
- **Acceptance**: Plan output contains explicit "tabs affected" and "skills invoked" sections
- **Dependencies**: 1.1
- **HITL gate**: G5
- **Effort**: 30 min

### Task 1.6 — Override `tasks.md` template

- **Inputs**: SpecKit default
- **Outputs**: `.specify/templates/commands/tasks.md` emitting per-tab tasks with sync rules baked in
- **Acceptance**: Generated tasks.md groups tasks by tab and labels each as live or manual-sync
- **Dependencies**: 1.5
- **HITL gate**: G5
- **Effort**: 30 min

**Phase 1 total**: ~2.5 hours.

---

## Phase 2 — SpecKit Extension scaffolding

Build the 6 custom slash commands.

### Task 2.1 — Create the Extension skeleton

- **Inputs**: SpecKit installed
- **Outputs**: `.specify/extensions.yml` with all 6 command names listed + `hooks: before_build: check_drift_trio, before_handoff: check_drift_trio`
- **Acceptance**: `specify extension list` shows `prototype-builder-ext`
- **Dependencies**: Phase 1 complete
- **HITL gate**: G5
- **Effort**: 15 min

### Task 2.2 — Implement `/build`

- **Inputs**: spec.md, plan.md, tasks.md from current feature; `./design-system/`
- **Outputs**: `.specify/extensions/commands/build.md`
- **Acceptance**: Dry-run `/build` on a stub spec produces a populated Tab 1 in `template.html`; trio drift check fires before write
- **Dependencies**: 2.1
- **HITL gate**: G5; also G2/G3 if test surfaces DS or stack issues
- **Effort**: 1.5 hours

### Task 2.3 — Implement `/sync.flow`

- **Inputs**: spec.md, plan.md, `craft-connect-flow` skill
- **Outputs**: `.specify/extensions/commands/sync.flow.md`
- **Acceptance**: Dry-run on a stub produces SVG flow + N user stories matching the flow paths
- **Dependencies**: 2.1
- **HITL gate**: G5
- **Effort**: 1.5 hours

### Task 2.4 — Implement `/sync.erd`

- **Inputs**: spec.md, plan.md; ERD guardrails from `01-srs.md` section 3 / FR-3 / approved guardrails
- **Outputs**: `.specify/extensions/commands/sync.erd.md`
- **Acceptance**: Dry-run produces Mermaid `erDiagram` passing all 5 ERD guardrails (or warns explicitly)
- **Dependencies**: 2.1
- **HITL gate**: G5
- **Effort**: 1 hour

### Task 2.5 — Implement `/handoff`

- **Inputs**: Tab 1 HTML, `./design-system/`, `design-critics` skill
- **Outputs**: `.specify/extensions/commands/handoff.md`
- **Acceptance**: Dry-run on a stub Tab 1 produces the 7:3 split with right panel showing **spec tokens + sizing only** (no code); drift check fires before write
- **Dependencies**: 2.2
- **HITL gate**: G5
- **Effort**: 2 hours

### Task 2.6 — Implement `/skills.refresh`

- **Inputs**: existing `.claude/skills/` clone, repo URL + pinned tag from constitution.md
- **Outputs**: `.specify/extensions/commands/skills.refresh.md`
- **Acceptance**: Running `/skills.refresh` against an outdated clone proposes the latest tag and updates on approval
- **Dependencies**: 2.1, 4.1 (clone exists)
- **HITL gate**: G5
- **Effort**: 1 hour

### Task 2.7 — Implement `/check.drift`

- **Inputs**: current `template.html`, `constitution.md`
- **Outputs**: `.specify/extensions/commands/check.drift.md`
- **Acceptance**: Running on a planted-drift template surfaces the violations; running on clean template returns "no drift"
- **Dependencies**: 2.1, 5.x (drift logic)
- **HITL gate**: G5
- **Effort**: 1 hour

**Phase 2 total**: ~7 hours.

---

## Phase 3 — Template wiring

Connect SpecKit outputs to `template.html` tabs.

### Task 3.1 — Copy `template.html` into Preset assets

- **Inputs**: existing `template.html` from `prototype-builder/`
- **Outputs**: Preset includes the template; `specify init` copies it to `./prototype/template.html`
- **Acceptance**: Fresh `specify init` produces a working empty-state `template.html`
- **Dependencies**: Phase 1 complete
- **HITL gate**: G5
- **Effort**: 30 min

### Task 3.2 — Inject SpecKit-output hooks into template

- **Inputs**: `template.html`; `.specify/` artifact paths
- **Outputs**: Modified `template.html` with build-time reads from `.specify/` markdown files
- **Acceptance**: After running `/speckit.constitution` + `/speckit.specify`, Tab 2 shows populated Overview and Principles
- **Dependencies**: 3.1, 1.2, 1.3
- **HITL gate**: G5 + visual check by Danh
- **Effort**: 2 hours

### Task 3.3 — Wire Tab 2 sub-sections

- **Inputs**: Tab 2 sub-section schema from `02-architecture.md` section 7
- **Outputs**: Tab 2 renders Overview, User Insights, UI Logic Trade-offs, Others
- **Acceptance**: All 4 sub-sections render, empty ones show empty-state copy
- **Dependencies**: 3.2
- **HITL gate**: G5 + visual check
- **Effort**: 1 hour

### Task 3.4 — Wire Tab 4 dual-view + 7:3 split

- **Inputs**: Tab 4 internals spec from `02-architecture.md` section 7
- **Outputs**: Tab 4 has Component / Screen toggle; Screen view uses CSS grid 7:3
- **Acceptance**: Toggle works; element click on left updates spec panel on right; right panel shows tokens + sizing only
- **Dependencies**: 3.1
- **HITL gate**: G5 + visual check (this is the most visually complex piece)
- **Effort**: 3 hours

**Phase 3 total**: ~6.5 hours.

---

## Phase 4 — Skill clone mechanism

Wire the external skill repo into init.

### Task 4.1 — Init script: clone with pinned tag

- **Inputs**: repo URL + pinned tag from presets.yml
- **Outputs**: init step that runs `git clone --depth 1 --branch <tag> <url> ./.claude/skills`
- **Acceptance**: Fresh `specify init` produces populated `./.claude/skills/`
- **Dependencies**: Phase 0 complete, Phase 1 complete
- **HITL gate**: G5
- **Effort**: 45 min

### Task 4.2 — Failure handling (G4)

- **Inputs**: clone exit code
- **Outputs**: hard-fail path with FR-5 error message
- **Acceptance**: Pointing the URL at a non-existent repo produces exact error from FR-5
- **Dependencies**: 4.1
- **HITL gate**: G4 (when triggered)
- **Effort**: 30 min

### Task 4.3 — Required-skills verification

- **Inputs**: required-skills list from `04-orchestrator.md` section 2
- **Outputs**: post-clone verification that each required skill has `SKILL.md`
- **Acceptance**: Missing any required skill → hard fail with the missing list
- **Dependencies**: 4.1
- **HITL gate**: G4
- **Effort**: 45 min

**Phase 4 total**: ~2 hours.

---

## Phase 5 — Drift detection implementation

The hardest correctness work in the system.

### Task 5.1 — Trio-touching detector

- **Inputs**: detection rules from `04-orchestrator.md` section 3.1
- **Outputs**: detector function used by `before_build` and `before_handoff` hooks
- **Acceptance**: 10 test prompts: 6 trio-touching, 4 not → detector classifies all correctly
- **Dependencies**: Phase 2 complete
- **HITL gate**: G5
- **Effort**: 1.5 hours

### Task 5.2 — Principle loader with session cache

- **Inputs**: `.specify/memory/constitution.md`
- **Outputs**: loader that parses Principles section, caches result for the session
- **Acceptance**: Repeated calls within a session don't re-parse the file
- **Dependencies**: 5.1
- **HITL gate**: G5
- **Effort**: 1 hour

### Task 5.3 — Diff procedure

- **Inputs**: principles list + proposed write payload
- **Outputs**: per-principle contradiction checker
- **Acceptance**: Given a known-contradicting payload, returns the matching principle(s)
- **Dependencies**: 5.2
- **HITL gate**: G5
- **Effort**: 2.5 hours

### Task 5.4 — Pause-and-ask UX

- **Inputs**: contradiction list from 5.3
- **Outputs**: pause output matching exactly the shape in `04-orchestrator.md` section 3.3
- **Acceptance**: A planted violation produces the exact UX; silence does not auto-approve
- **Dependencies**: 5.3
- **HITL gate**: G1 (when triggered) + G5 (review)
- **Effort**: 1 hour

### Task 5.5 — Integration test

- **Inputs**: Phase 5.1–5.4 complete
- **Outputs**: end-to-end drift test on a sample project
- **Acceptance**: Planted violation triggers pause; revised prompt clears the pause; clean prompt proceeds without pause
- **Dependencies**: 5.4
- **HITL gate**: G5
- **Effort**: 1 hour

**Phase 5 total**: ~7 hours.

---

## Phase 6 — Tab sync rules implementation

Wire the auto vs manual sync rules.

### Task 6.1 — Auto-sync triggers (Tab 1, Tab 2, Tab 4-C)

- **Inputs**: command output detection
- **Outputs**: after-write hook that always updates the trio when /build, /speckit.constitution, /speckit.specify, /speckit.clarify, /speckit.plan run
- **Acceptance**: Running any of those commands updates all 3 trio tabs without manual sync
- **Dependencies**: Phase 5 complete (drift check must precede auto-sync)
- **HITL gate**: G5
- **Effort**: 1.5 hours

### Task 6.2 — Manual-sync gates (Tab 3, Tab 4-S, Tab 5)

- **Inputs**: command-name allowlist
- **Outputs**: enforcement that Tab 3 / Tab 4-S / Tab 5 only update on their named commands
- **Acceptance**: Random prompts touching flow/handoff/erd keywords do NOT update those tabs
- **Dependencies**: 6.1
- **HITL gate**: G5
- **Effort**: 1 hour

### Task 6.3 — Stale badge logic

- **Inputs**: tab last-updated timestamps
- **Outputs**: in Tab 3 / Tab 4-S / Tab 5, show "Stale: last synced N prompts ago" if N > threshold
- **Acceptance**: After 10 trio-touching prompts without `/sync.flow`, Tab 3 shows "Stale: 10 prompts ago"
- **Dependencies**: 6.2
- **HITL gate**: G5
- **Effort**: 1 hour

### Task 6.4 — End-to-end smoke test

- **Inputs**: Phases 1–6 complete
- **Outputs**: 20-prompt session against a test project
- **Acceptance**:
  - Trio auto-syncs on every relevant prompt
  - Decoupled tabs stay frozen
  - Drift check fires on planted violation
  - Stale badge appears at threshold
- **Dependencies**: 6.3
- **HITL gate**: G5
- **Effort**: 1.5 hours

**Phase 6 total**: ~5 hours.

---

## Phase 7 — Acceptance test on real prototype

### Task 7.1 — Pick a test case

- **Inputs**: none
- **Outputs**: a real but simple test prototype goal — recommended: "Login screen with email + password, error states, success redirect"
- **Acceptance**: Test case is small enough to ship in one session, complex enough to exercise all 5 tabs
- **Dependencies**: Phase 6 complete
- **HITL gate**: G5 — Danh approves the test case
- **Effort**: 15 min (decision)

### Task 7.2 — Run init

- **Inputs**: clean directory
- **Outputs**: scaffolded project with all 5 tabs empty
- **Acceptance**: Init completes without manual intervention beyond prompted decisions
- **Dependencies**: 7.1
- **HITL gate**: G5
- **Effort**: 5 min

### Task 7.3 — Full workflow run

- **Inputs**: scaffolded project
- **Outputs**: `/speckit.constitution` → `/speckit.specify` → `/speckit.clarify` → `/speckit.checklist` → `/build` → `/sync.flow` → `/handoff` → `/sync.erd`
- **Acceptance**: All 5 tabs populated; all commands ran without errors
- **Dependencies**: 7.2
- **HITL gate**: G5 after each command
- **Effort**: 1.5 hours

### Task 7.4 — Drift trigger test

- **Inputs**: populated project from 7.3
- **Outputs**: deliberately send a prompt that contradicts a Tab 2 principle
- **Acceptance**: Drift detected, pause-and-ask fires correctly per 04-orchestrator.md section 3.3
- **Dependencies**: 7.3
- **HITL gate**: G1
- **Effort**: 30 min

### Task 7.5 — Ship decision

- **Inputs**: all test results
- **Outputs**: signed-off Preset, ready for re-use across future prototypes
- **Acceptance**: All success criteria from `01-srs.md` section 6 pass
- **Dependencies**: 7.4
- **HITL gate**: **G6 — final acceptance**
- **Effort**: Danh's decision

**Phase 7 total**: ~2.5 hours + decision time.

---

## Aggregate effort estimate

| Phase | Effort |
|-------|-------|
| 0 (Danh) | 40 min |
| 1 | 2.5 h |
| 2 | 7 h |
| 3 | 6.5 h |
| 4 | 2 h |
| 5 | 7 h |
| 6 | 5 h |
| 7 | 2.5 h |
| **Total** | **~32 hours of focused work** |

Realistic calendar time: 1 to 2 weeks at 2–4 focused hours per day.

---

## Per-task template (reference for any future task additions)

When adding tasks to this file, use this template:

```markdown
### Task X.Y — Short title

- **Inputs**: what files/state required to start
- **Outputs**: what files/state exist after completion
- **Acceptance**: testable condition that proves the task is done
- **Dependencies**: which tasks must precede this one
- **HITL gate**: which gate (if any) fires after this task
- **Effort**: rough estimate
```

---

## When to stop and ask Danh

- Any acceptance criterion seems unachievable → stop, propose 2–3 alternatives
- Any dependency task produced unexpected output → stop, review with Danh
- Any HITL gate fires → stop and wait (this is the whole point of gates)
- Effort estimates are blown by more than 2× → stop, re-scope with Danh
- Any required skill from `04-orchestrator.md` is missing → stop, run `/skills.refresh` or escalate

Default behavior: stop more often, not less.
