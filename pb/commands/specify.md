---
description: Produce the spec / PRD for the prototype, native (no SpecKit). Prototype-shaped user stories with JTBD, tabs affected, and custom organisms.
---

# /pb:specify

Expand `memory/prd.md` into a structured spec, natively (no SpecKit).

## 1 · Write the spec
Invoke `think-critique-prd` (push on goals / personas / gaps), then `think-clarify` (ask only what's
load-bearing). Produce `memory/spec.md`:
- **Objective** — one paragraph.
- **User stories** — prototype-shaped, each with a **JTBD**, the **tabs affected**, and any **custom
  organisms** it needs.
- **Edge cases** — the states the prototype must show.

Honor the Stack Lock + DS Lock in `memory/constitution.md`.

## 2 · Fold the Tab-2 sync (no hook)
Write the spec's **Objective** into `registry.json` → `meta.overview.objectives`. (Replaces the v0.4.0
`after_specify` → `sync-tab2` hook.) **Do not render.**

## Result
`memory/spec.md` written; Tab-2 Objective synced. Next: `/pb:clarify` or `/pb:plan`.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
