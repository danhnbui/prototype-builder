---
description: Clarify underspecified areas of a prototype spec. Captures clarifications into User Insights and UI Logic Trade-offs sections that map directly into Tab 2 of template.html.
handoffs:
  - label: Plan Implementation
    agent: speckit.plan
    prompt: Plan the prototype implementation based on the clarified spec.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Pre-Execution Checks

**Check for extension hooks (before clarify update)**:
- Check if `.specify/extensions.yml` exists in the project root.
- If it exists, read it and look for entries under the `hooks.before_clarify` key.
- Follow the standard SpecKit hook discovery / execution behavior (optional vs mandatory, skip on parse errors).
- If no hooks registered, skip silently.

## Outline

You are creating or updating `.specify/specs/[###-feature]/clarify.md`. For prototype work, this file **MUST** include three distinct sections that map directly into Tab 2 (Project Summary) sub-sections of `prototype/template.html`:

### 1. User Insights (Tab 2.2)
Capture research findings, quantitative data, and qualitative observations relevant to the prototype's hypothesis.

Sub-sections (all optional; include only what applies):
- **Quantitative Data**: surveys, analytics, A/B test results — with source citations
- **Research Summary Report**: qualitative findings from user interviews / usability tests
- **Executive Summary**: 1-paragraph synthesis tying insights to the prototype's Objective

### 2. UI Logic Trade-offs (Tab 2.3)
Document trade-offs the team made during clarification. Each trade-off:

```
### Trade-off N — [Brief title]

**Question**: [What was unclear?]
**Options considered**:
1. [Option A] — pros: [list]; cons: [list]
2. [Option B] — pros: [list]; cons: [list]
**Decision**: [Chosen option]
**Why**: [1–2 sentences]
**Affects tabs**: [Tab 1 / Tab 4-C — list]
```

### 3. Resolved Ambiguities
List `NEEDS CLARIFICATION` items from the spec that this clarify pass resolved.

## Execution flow

1. **Load** the current spec.md from `.specify/specs/[active]/spec.md`.
2. **Identify** all `NEEDS CLARIFICATION` markers and ambiguous statements.
3. **Ask the user** about each ambiguity, ordering by priority (P1 stories first).
4. **For each clarified item**, decide whether it's a User Insight, a UI Logic Trade-off, or just a spec edit:
   - User Insight: external evidence about user behavior / preferences
   - UI Logic Trade-off: an internal design decision among alternatives
   - Spec edit: clarification that just updates spec.md (no clarify.md entry needed)
5. **Update** `.specify/specs/[active]/spec.md` if the clarification changes its content.
6. **Write or update** `.specify/specs/[active]/clarify.md` with the three-section structure above.

## After writing

Output a summary:
- Number of User Insights captured
- Number of UI Logic Trade-offs captured
- Number of `NEEDS CLARIFICATION` items resolved (and any remaining)
- Note: *"Tab 2 will auto-sync these sections on the next `/build`."*

## Important rules

- **NEVER fabricate User Insights** — only record what the user supplied or what's in linked research artifacts.
- **NEVER record a Trade-off without listing the rejected options** — the rejected paths are the value of the document.
- **NEVER write code or implementation details** into clarify.md — that's plan.md's job.
