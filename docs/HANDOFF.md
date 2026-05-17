# HANDOFF — Prototype Builder × SpecKit

**Audience**: Claude Code (autonomous executor)
**Author**: Danh N. Bui — Product Design Lead, PropertyGuru Vietnam
**Status**: Approved for execution after Phase 0 confirmation
**Version**: v1.0 (locked from outline v0.3)

---

## What this is

A reusable system for building serious UX-test prototypes. SpecKit (the open-source spec-driven development toolkit from GitHub) provides the workflow shell. A custom Preset and Extension bend it toward prototype work. A single-file `template.html` with 5 documentation tabs is the deliverable. Skills are pulled from an external GitHub repo at project init.

You — Claude Code — are reading this because Danh wants to build this system once and reuse it across many prototype projects.

---

## How to use this package

Read these files in order:

| Step | File | Purpose |
|------|------|---------|
| 1 | `HANDOFF.md` (this file) | Entry point, hard rules, gate summary |
| 2 | `01-srs.md` | Requirements — what to build, what NOT to build |
| 3 | `02-architecture.md` | System shape — layers, folders, file roles |
| 4 | `03-data-flow.md` | How data moves — Mermaid diagrams |
| 5 | `04-orchestrator.md` | Control flow — skill firing, HITL gates, drift logic |
| 6 | `05-execution-plan.md` | Step-by-step tasks with acceptance criteria |

Then execute `05-execution-plan.md` phase by phase. Stop at every HITL gate.

---

## Hard rules (NEVER violate)

1. **Never start Phase 1 until Phase 0 is confirmed done by Danh.** Phase 0 is the skill repo sync — it lives outside your control. Wait for explicit confirmation in chat.
2. **Never bypass a HITL gate.** When the plan says "wait for approval," wait.
3. **Never auto-sync Tab 3, Tab 4-Screen, or Tab 5.** These only refresh on explicit `/sync.flow`, `/handoff`, or `/sync.erd` commands.
4. **Never generate code snippets in Tab 4-Screen's right panel.** Spec tokens + sizing only. Code lives in Tab 1, referenced by line number.
5. **Never proceed past a drift-trio violation without explicit approval.** Tab 1, Tab 2, and Tab 4-Component must stay in lockstep. If any prompt would break that, pause and ask.
6. **Never fork SpecKit.** All customization happens through Preset + Extension. Forking is a permanent maintenance liability.
7. **Never declare `template.html` "done" if it exceeds 3,000 lines.** That's the migration threshold to a Vite scaffold.
8. **Never invent a new SpecKit slash command.** If a behavior doesn't fit `/speckit.*` or one of the 6 custom commands defined in `04-orchestrator.md`, ask Danh.

---

## Assumptions locked from prior decisions

| # | Decision |
|---|----------|
| 1 | Architecture: 2 layers (SpecKit + template.html) |
| 2 | Trio = Tab 1 + Tab 2 + Tab 4-Component |
| 3 | Decoupled = Tab 3, Tab 4-Screen, Tab 5 |
| 4 | Skill source: `github.com/danhnbui/agent-skill-set` (does not yet exist) |
| 5 | Skill pinning: pinned tag at init, `/skills.refresh` for updates |
| 6 | Approval signal: prompt + Enter in chat |
| 7 | Drift detection: AI self-check every turn, **scoped to trio-touching prompts only** |
| 8 | Tab 4 right panel: spec tokens + sizing only |
| 9 | Design system: confirmed at setup, pulled to `./design-system/`, no random DS |
| 10 | Code language + framework: declared at setup, locked thereafter |
| 11 | One repo per prototype |
| 12 | Output folder: SpecKit conventions + `.claude/skills/`, `./design-system/`, `./prototype/` |

---

## HITL gates summary

| Gate | When it fires | What you do |
|------|--------------|-------------|
| **G0** | Phase 0 not confirmed | STOP. Wait for "skill repo ready" from Danh. |
| **G1** | Drift between Tab 1 / Tab 2 / Tab 4-C | Pause, surface conflict, ask. |
| **G2** | Design system override attempted | Pause, ask if Danh wants to extend DS or override. |
| **G3** | Code language/framework switch attempted | Pause, ask. Locked at setup. |
| **G4** | Skill repo unreachable at init | HARD FAIL with clear message. |
| **G5** | After each Phase 1–6 task | Brief check-in before next task. |
| **G6** | Phase 7 (acceptance test) | Final review before declaring "ship the preset". |

---

## What success looks like

- `specify init --preset prototype-builder` runs end-to-end on a clean machine
- All 5 tabs scaffold correctly in `prototype/template.html`
- Trio drift check fires on a planted violation, AI pauses
- Tab 3 / Tab 4-Screen / Tab 5 stay frozen until their `/sync` commands run
- A real prototype (Phase 7 test case) ships through the system without Claude Code asking Danh anything outside the defined HITL gates
- All custom slash commands respond to dry-runs with no errors

---

## When to escalate to Danh

| Situation | Action |
|-----------|--------|
| A locked assumption appears wrong in practice | Stop, ask in chat |
| An acceptance criterion can't be met | Stop, propose 2–3 alternatives |
| A skill referenced in `04-orchestrator.md` is missing from the cloned repo | Stop, list what's missing |
| You discover a 13th decision needed | Stop, draft the question |
| Phase 7 test case fails | Stop, show the failure mode |

Never silently work around a problem. Always surface and ask.

---

## File map (this package)

```
/mnt/user-data/outputs/prototype-builder-handoff/
├── HANDOFF.md              ← you are here
├── 01-srs.md               ← requirements
├── 02-architecture.md      ← system shape
├── 03-data-flow.md         ← data flow diagrams
├── 04-orchestrator.md      ← control flow
└── 05-execution-plan.md    ← actionable task list
```

When Danh has reviewed and committed to a per-prototype repo, this whole package gets copied into `docs/` at the root of that repo.

---

## Provenance

This package was produced by Claude (chat) through 7 rounds of outline review with Danh. Every locked decision in the table above traces back to an explicit chat exchange. If you find a contradiction between this package and Danh's spoken intent, **Danh wins** — flag it and pause.
