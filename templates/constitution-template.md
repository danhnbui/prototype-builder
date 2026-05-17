# [PROJECT_NAME] Constitution

<!-- Example: My Photo Album Prototype Constitution -->

## Principles

<!--
  3–7 principles, each 1–3 lines. Keep them short — drift-check token cost
  scales with principle length. Shorter principles = cheaper drift checks.
-->

### 1. [PRINCIPLE_1_NAME]
<!-- Example: Mobile-first — every layout assumes a small screen as the default; desktop is a progressive enhancement. -->
[PRINCIPLE_1_DESCRIPTION]

### 2. [PRINCIPLE_2_NAME]
<!-- Example: Single-tap primary action — every screen has exactly one obvious primary CTA. -->
[PRINCIPLE_2_DESCRIPTION]

### 3. [PRINCIPLE_3_NAME]
[PRINCIPLE_3_DESCRIPTION]

<!--
  Add more principles as needed.
  Number them sequentially so the drift check can reference them by ID.
-->

---

## Stack Lock

Locked at init. Changes require HITL gate G3 approval.

- **Language**: [LANGUAGE]
  <!-- Example: HTML / React / Vue / Svelte / SwiftUI / Flutter / other -->
- **Framework**: [FRAMEWORK]
  <!-- Example: vanilla / Vite / Next.js / Nuxt / Remix / native / other -->

Any code generation in `/speckit.prototype-builder.build` that deviates from this stack MUST trigger a pause-and-ask.

---

## Design System Lock

Locked at init. Changes (extending or overriding) require HITL gate G2 approval.

- **Source**: [DS_SOURCE]
  <!-- Example: https://github.com/propertyguru/hive-ui-core, or local path, or built-in (HIVE / Material / shadcn) -->
- **Local path**: ./design-system/
- **Confirmed at**: [DS_CONFIRMED_DATE]
  <!-- ISO format: YYYY-MM-DD -->

Any styling outside this DS (inline styles, external CSS imports, hex colors not in tokens.json) MUST trigger a pause-and-ask.

---

## Skill Pinning

Skills are cloned from the agent-skill-set repo at init.

- **Source**: [SKILL_REPO_URL]
  <!-- Example: https://github.com/danhnbui/agent-skill-set -->
- **Pinned tag**: [SKILL_PINNED_TAG]
  <!-- Example: v0.1.0 -->
- **Local path**: ./.claude/skills/

Use `/speckit.prototype-builder.skills-refresh` to upgrade to a newer tag. The bump requires explicit approval.

---

## Governance

- This constitution supersedes all other project practices.
- Amendments require explicit user approval and a version bump.
- Per-prompt drift detection is scoped to **trio-touching prompts only** (mentions of Tab 1, Tab 2, or Tab 4-Component concepts). Decoupled tabs (3, 4-Screen, 5) skip the check.
- All custom slash commands (`/speckit.prototype-builder.*`) follow the same HITL gate discipline as core SpecKit commands.

---

**Version**: [CONSTITUTION_VERSION] | **Ratified**: [RATIFICATION_DATE] | **Last Amended**: [LAST_AMENDED_DATE]
<!-- Example: Version: 1.0.0 | Ratified: 2026-05-16 | Last Amended: 2026-05-16 -->
