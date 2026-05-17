---
description: Create or update the prototype project constitution. Captures Principles (used by drift detection), Stack Lock (language + framework), and Design System Lock — and keeps them in sync with dependent templates.
handoffs:
  - label: Build Specification
    agent: speckit.specify
    prompt: Implement the prototype feature based on the updated constitution. I want to build...
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Pre-Execution Checks

**Check for extension hooks (before constitution update)**:
- Check if `.specify/extensions.yml` exists in the project root.
- If it exists, read it and look for entries under the `hooks.before_constitution` key.
- If the YAML cannot be parsed or is invalid, skip hook checking silently and continue normally.
- Filter out hooks where `enabled` is explicitly `false`. Treat hooks without an `enabled` field as enabled by default.
- For each remaining hook, do **not** attempt to interpret or evaluate hook `condition` expressions:
  - If the hook has no `condition` field, or it is null/empty, treat the hook as executable.
  - If the hook defines a non-empty `condition`, skip the hook and leave condition evaluation to the HookExecutor implementation.
- For each executable hook, output the standard hook block (optional vs mandatory) per SpecKit core behavior.
- If no hooks are registered or `.specify/extensions.yml` does not exist, skip silently.

## Outline

You are updating the project constitution at `.specify/memory/constitution.md`. For prototype projects, this file **MUST** include three sections beyond the generic constitution template:

1. **Principles** — used by the inline drift check in `/speckit.prototype-builder.build` and `.handoff`
2. **Stack Lock** — language + framework, immutable after init (HITL gate G3 on change attempts)
3. **Design System Lock** — DS source recorded at init (HITL gate G2 on override attempts)

### Execution flow

1. **Load** `.specify/memory/constitution.md`.
   - If it does not exist, copy from `.specify/templates/constitution-template.md`.
   - Identify all `[PLACEHOLDER]` tokens.

2. **Collect/derive values**:
   - From the user's input above (highest priority).
   - From the existing repo (README, prior constitution).
   - If a placeholder remains uncertain, mark it `TODO(danh)` rather than guessing.

3. **For the Principles section** (required for prototype work):
   - List 3–7 principles as `### N. [Principle Name]` headers.
   - Each principle: 1–3 lines maximum. Keep them short (shorter principles = lower drift-check token cost per [03-data-flow.md](https://github.com/danhnbui/spec-kit-extension-prototype-builder/blob/main/docs/03-data-flow.md) §6 mitigation).
   - Examples:
     - `### 1. Mobile-first` — all layouts assume small screen as default
     - `### 2. Single-tap primary action` — every screen has one obvious primary CTA
     - `### 3. No animated transitions over 200ms` — perceived performance over polish

4. **For the Stack Lock section** (required):
   - Prompt the user (or use init args) for:
     - `Language`: HTML / React / Vue / Svelte / SwiftUI / Flutter / other
     - `Framework`: vanilla / Vite / Next.js / Nuxt / Remix / native / other
   - Write them under `## Stack Lock` as `**Language**: X` / `**Framework**: Y`.
   - State explicitly: *"These values are locked. Changes require HITL gate G3 approval."*

5. **For the Design System Lock section** (required):
   - Prompt the user for the DS source: git URL / local path / built-in (HIVE / Material / shadcn / custom).
   - Write under `## Design System Lock`: `**Source**: <url or path>`, `**Local path**: ./design-system/`, `**Confirmed at**: <ISO date>`.
   - State explicitly: *"Any styling outside this DS triggers HITL gate G2."*

6. **Set version metadata**:
   - `CONSTITUTION_VERSION`: semver bump (PATCH for wording, MINOR for new principles/sections, MAJOR for breaking governance changes).
   - `RATIFICATION_DATE`: today, in ISO format (YYYY-MM-DD), if first ratification.
   - `LAST_AMENDED_DATE`: today.

7. **Propagate** to dependent artifacts:
   - `.specify/templates/plan-template.md` Stack Lock + Constitution Check sections must match.
   - Any existing `spec.md` / `plan.md` files MUST be re-read and flagged if a new principle contradicts them.

8. **Write** the updated constitution.

9. **Confirm to user**:
   - Output a summary: number of principles, stack lock values, DS source, version.
   - Note: *"Drift check will fire on any prompt touching Tab 1, Tab 2, or Tab 4-Component. Decoupled tabs (3, 4-Screen, 5) skip the check."*

## Important rules

- **NEVER omit Principles, Stack Lock, or DS Lock sections** even if the user didn't provide values — use `TODO(danh)` placeholders rather than skipping.
- **NEVER set a `LAST_AMENDED_DATE` earlier than `RATIFICATION_DATE`**.
- **NEVER fork the constitution into multiple files**; this single file is the source of truth.
