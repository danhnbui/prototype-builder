---
description: Scaffold a new Product Builder prototype — PRD intake (Q&A or file, never blank), set Stack + DS locks, seed registry.json + memory/. Optional --import <bundle> to ingest a context hand-off.
---

# /pb:init

Scaffold a new prototype **in the current directory**. PRD intake is **never blank**.

## 0 · Flags
- `--import <bundle>` — ingest a context bundle from `/pb:hand-off --context` instead of doing intake (step 6).

## 1 · PRD intake (never blank)
Never start empty. Source it one of two ways:
- **File** — a path in `$ARGUMENTS` or a `docs/prd/*.md`: read it; invoke `ref-prd` to parse and
  `think-critique-prd` to surface gaps.
- **Q&A** — otherwise ask, one at a time: (1) the product/feature in a line; (2) who it's for;
  (3) the core problem; (4) the 3–6 key screens; (5) what success looks like. Use `think-clarify` to
  decide what genuinely needs asking vs a sensible default.

Write a short PRD (objective + key screens + success criteria) to `memory/prd.md`.

## 2 · Set the locks (confirm with the user)
- **Stack Lock** — language + framework (e.g. TypeScript + React).
- **Design System Lock** — name + source (git URL / local path / built-in).

Write `memory/constitution.md` from `${CLAUDE_PLUGIN_ROOT}/template/constitution.template.md`, filling
Stack Lock + DS Lock + a first cut of Principles (from the PRD + DS rules). Keep it lean.

## 3 · Seed the registry
Copy `${CLAUDE_PLUGIN_ROOT}/template/registry.template.json` → `registry.json`; set `meta.name`. Leave
`tokens` / `components` / `screens` empty — `/pb:build` fills them.

## 4 · Seed memory + design system
- `memory/decisions.md` from `${CLAUDE_PLUGIN_ROOT}/template/decisions.template.md`.
- `design-system/{name}/{name}.md` — a starting DS reference (foundations + an empty component index +
  rules R0–R4 + the naming contract). The full template lands in Phase 5.

## 5 · Fold the Tab-2 sync (no hook)
Write into `registry.json`: `meta.overview.objectives` = the PRD objective; `meta.overview.principles`
= the constitution Principles as `[{num,title,body}]`. This is the Project-Summary sync the v0.4.0
`after_*` hooks used to do — it now lives here. **Do not render yet.**

## 6 · `--import <bundle>` (alternative on-ramp)
If set, skip 1–5: read the bundle (`registry.json` + `design-system/` + `memory/constitution.md` +
`memory/decisions.md`), copy it into the new project, confirm the locks. Ready to `/pb:build`.

## Result
A seeded project — non-empty `memory/prd.md`, locks set, `registry.json` seeded, `memory/decisions.md`,
`design-system/{name}/`. Next: `/pb:specify` (expand) or `/pb:build` (start building).
