# 01 — SRS: Software Requirements Specification

**Purpose**: Define what the Prototype Builder × SpecKit integration must do, must NOT do, and how we know it works.

---

## 1. Purpose & scope

### 1.1 Goal
Provide a reusable spec-driven workflow that produces single-file HTML prototypes with built-in documentation, optimized for usability testing and handoff to engineering.

### 1.2 In scope
- A SpecKit Preset that customizes `/speckit.*` phase templates for prototype work
- A SpecKit Extension that adds 6 custom slash commands for prototype-specific actions
- Integration with an external skill repo for design/critique skills
- Drift detection across a defined trio of artifacts
- Scaffolding of a 5-tab `template.html` file at project init

### 1.3 Out of scope
- Production application deployment
- Multi-prototype workspace (one repo per prototype only)
- Non-Claude-Code agent support (Cursor, Copilot, etc.)
- Cloud sync or collaboration features
- Real-time multi-user editing
- Server-side state (everything is single-file or local filesystem)

---

## 2. Actors

| Actor | Role |
|-------|------|
| **Danh** | Project owner, decides intent, approves at HITL gates |
| **Claude Code** | Autonomous executor of the spec workflow |
| **Future skill consumers** | Other projects that may clone the same skill repo (not blocked, not first-class) |

---

## 3. Functional requirements

### FR-1 — SpecKit Preset for prototype-builder

The system MUST provide a SpecKit Preset installable via `specify preset add prototype-builder` that:

- Overrides the default templates for `/speckit.constitution`, `/speckit.specify`, `/speckit.clarify`, `/speckit.plan`, `/speckit.tasks`
- Maps each phase's output to specific sections of Tab 2 (Project Summary)
- Carries the 12 locked assumptions as preset metadata

**Acceptance**: running `specify preset add prototype-builder` followed by `specify init` produces a project with the prototype-shaped templates active.

### FR-2 — Custom slash commands

The system MUST add the following slash commands via SpecKit Extension:

| Command | Action |
|---------|--------|
| `/build` | Generate or update Tab 1 (Prototype) from current spec + plan |
| `/sync.flow` | Generate or update Tab 3 (User Flow) as zoomable SVG + user-story list |
| `/sync.erd` | Generate or update Tab 5 (ERD) as Mermaid `erDiagram` |
| `/handoff` | Generate or update Tab 4 Screen view (the 7:3 split) |
| `/skills.refresh` | Re-clone the pinned skill repo, update local `.claude/skills/` |
| `/check.drift` | Manual drift audit across the trio |

**Acceptance**: each command is callable in Claude Code and produces the documented output without errors.

### FR-3 — 5-tab template scaffolding

At `specify init`, the system MUST copy `template.html` into `./prototype/template.html` with:

- Tab 1 (Prototype) — empty placeholder ready for `/build`
- Tab 2 (Project Summary) — empty sections for Overview, User Insights, UI Logic Trade-offs, Others
- Tab 3 (User Flow) — empty canvas ready for `/sync.flow`
- Tab 4 (Design Handoff) — Component view + Screen view toggle, both empty
- Tab 5 (ERD) — empty placeholder ready for `/sync.erd`

**Acceptance**: opening the scaffolded `template.html` in a browser shows all 5 tabs with intact navigation and empty-state messaging.

### FR-4 — Drift detection (Option A, scoped)

When any prompt touches Tab 1, Tab 2, or Tab 4-Component, the system MUST:

1. Detect that the prompt touches the trio
2. Load the current Tab 2 Objectives and Principles
3. Compare the proposed write against those principles
4. If a contradiction is detected, pause and surface the conflict
5. Wait for explicit prompt + Enter approval before proceeding

When a prompt touches only Tab 3, Tab 4-Screen, or Tab 5, the drift check is skipped.

**Acceptance**: a planted violation triggers a pause-and-ask; a non-violation proceeds silently.

### FR-5 — Skill repo clone at init

At `specify init`, the system MUST:

1. Attempt to clone `github.com/danhnbui/agent-skill-set` at the pinned tag (default `v0.1.0`)
2. Place the clone at `./.claude/skills/`
3. If unreachable, hard-fail with message: `"Skill repo not reachable. Confirm github.com/danhnbui/agent-skill-set exists and is accessible, then re-run init."`

**Acceptance**: clean clone produces a populated `.claude/skills/`; broken clone fails with the exact message above and a non-zero exit.

### FR-6 — Design system confirmation + pull at setup

At `specify init`, after skill clone succeeds, the system MUST:

1. Prompt: `"Design system source? (git URL / local path / built-in HIVE)"`
2. Pull/copy the chosen DS into `./design-system/`
3. Record the chosen DS in `.specify/memory/constitution.md`
4. Reject any later prompt that tries to use a DS other than the recorded one (G2 gate)

**Acceptance**: a chosen DS lives in `./design-system/`; attempts to introduce inline styles or external DS trigger a pause.

### FR-7 — Code language + framework declaration at setup

At `specify init`, after DS confirmation, the system MUST:

1. Prompt: `"Code language? (HTML / React / Vue / ...)"`
2. Prompt: `"Framework? (vanilla / Next.js / Vite / ...)"`
3. Record both in `.specify/memory/constitution.md`
4. Reject any later prompt that tries to switch language or framework (G3 gate)

**Acceptance**: the stack declaration is permanent; switch attempts trigger a pause.

### FR-8 — HITL pause-and-ask on objective drift

When G1, G2, or G3 fires, the system MUST:

1. Stop writing
2. Print the proposed write
3. Print the conflicting rule (from Tab 2 principles, DS lock, or stack lock)
4. Ask: `"Approve override? (yes / no / revise)"`
5. Wait for prompt + Enter
6. Only proceed on `yes`; revise on `revise`; cancel on `no`

**Acceptance**: each gate, when triggered, follows this protocol exactly.

---

## 4. Non-functional requirements

| ID | Requirement | Threshold |
|----|------------|-----------|
| NFR-1 | Drift check token budget | ≤30K tokens per 50-turn session (with scoping) |
| NFR-2 | One repo per prototype | No shared workspace |
| NFR-3 | Follow SpecKit directory conventions | `.specify/`, `templates/`, `extensions/` standard layout |
| NFR-4 | `template.html` size limit | <3,000 lines; flag for migration if exceeded |
| NFR-5 | Preset installable offline after first download | Cache the preset, no re-fetch needed |
| NFR-6 | Skill clone reproducibility | Pinned tag, not `main` |
| NFR-7 | Error messages must be actionable | Every failure names the file, the rule, and the fix |

---

## 5. Constraints

| Constraint | Source |
|-----------|--------|
| No fork of SpecKit | Decision lock #1 |
| No code in Tab 4-Screen right panel | Decision lock #8 |
| No auto-sync for Tab 3 / Tab 4-S / Tab 5 | Decision lock #3 |
| Skill repo URL fixed: `github.com/danhnbui/agent-skill-set` | Decision lock #7 |
| Drift trio scope only: Tab 1 + Tab 2 + Tab 4-Component | Decision lock #2 |

---

## 6. Success criteria (testable, in priority order)

1. **Init runs end-to-end on a clean machine** — `specify preset add prototype-builder && specify init --preset prototype-builder` completes without manual intervention beyond the prompted decisions (DS, language, framework).
2. **Drift check fires on a planted violation** — write a prompt that explicitly contradicts a Tab 2 principle; system pauses.
3. **Decoupled tabs stay frozen** — run 10 prompts that don't include `/sync.*` or `/handoff`; Tabs 3, 4-Screen, 5 remain at their last state.
4. **Phase 7 test prototype ships** — using a simple login-screen test case, run the full workflow start to finish; all 5 tabs populate.
5. **Skill commands work** — `/skills.refresh` re-pulls the pinned repo and updates `.claude/skills/`.
6. **Hard fail on missing repo** — point the preset at a non-existent URL; init exits with the documented error message.

---

## 7. Open requirements (deferred, not in v1.0)

| Item | Why deferred |
|------|-------------|
| Multi-prototype workspace | Different architecture, scope creep risk |
| Non-Claude-Code agent support | One agent, one optimization |
| Auto-migration to Vite when `template.html` >3K lines | Manual flag is enough for v1.0 |
| Web UI for `/sync` buttons | CLI is sufficient; you live in Claude Code |
| Analytics on drift-check trigger rate | Nice to have, not blocking |
