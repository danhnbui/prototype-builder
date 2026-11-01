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

**Line by line.** Save it as it is written, not after the spec is done (`${CLAUDE_PLUGIN_ROOT}/docs/canon.md`
§ *Line by line*): the Objective the moment it is settled — `slice.py set meta overview.objectives` — and each
principle the spec states as its own call, `slice.py append meta overview.principles`. Run
`serve.py registry.json --ensure` first if no preview is open, so there is a page to fill. An objective the
user has not agreed yet is a draft: `slice.py set meta overview.objectives --draft`, written for real once agreed,
then `slice.py drafts --clear`. About 2.5 s a line; never render.

## Result
`memory/spec.md` written; Tab-2 Objective synced. Next: `/pb:clarify` or `/pb:plan`.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
