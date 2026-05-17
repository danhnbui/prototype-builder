# Prototype Spec: [FEATURE NAME]

**Branch**: `[###-feature-name]` | **Created**: [DATE] | **Status**: Draft

**Input**: User description: "$ARGUMENTS"

---

## Objective *(Tab 2 → Overview > Objectives)*

In 1–3 sentences: what is this prototype trying to test, and with whom?

[OBJECTIVE]

---

## User Scenarios *(mandatory — prioritized P1, P2, P3)*

<!--
  IMPORTANT: User stories must be INDEPENDENTLY TESTABLE.
  Each story is a standalone slice of the prototype.
  Assign priorities (P1, P2, P3); P1 is the most critical.
-->

### User Story 1 — [Brief Title] (Priority: P1)

[Plain-language journey through the prototype]

**JTBD**: [What is the user trying to accomplish?]

**Why this priority**: [Value rationale tied to the Objective]

**Tabs affected**: [Tab 1 / Tab 4-Component — list]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [user action], **Then** [observable outcome in the prototype]
2. **Given** [initial state], **When** [user action], **Then** [observable outcome]

---

### User Story 2 — [Brief Title] (Priority: P2)

[Story]

**JTBD**: [What is the user trying to accomplish?]

**Why this priority**: [Value rationale]

**Tabs affected**: [list]

**Acceptance Scenarios**:

1. **Given** [state], **When** [action], **Then** [outcome]

---

### User Story 3 — [Brief Title] (Priority: P3)

[Story]

**JTBD**: [What is the user trying to accomplish?]

**Why this priority**: [Value rationale]

**Tabs affected**: [list]

**Acceptance Scenarios**:

1. **Given** [state], **When** [action], **Then** [outcome]

---

### Edge Cases

- What happens when [boundary condition]?
- How does the prototype handle [error scenario]?
- What's shown for [empty state / loading / unhappy path]?

---

## UI / Component Requirements *(inputs to Tab 4-Component)*

### Custom Organisms
List components that need variants beyond the design system. These will populate Tab 4-C.

- **[Organism name]**: [purpose], [variants needed]
- **[Organism name]**: [purpose], [variants needed]

### Existing DS Components
Components from `./design-system/` that this prototype uses as-is (no variants needed beyond DS defaults).

- [Component name]
- [Component name]

---

## Success Criteria *(Tab 2 → Overview > Success Criteria)*

<!--
  Define measurable, technology-agnostic outcomes.
  These are the hypotheses the prototype tests.
-->

- **SC-001**: [Measurable; e.g., "≥80% of testers complete primary flow on first attempt"]
- **SC-002**: [Hypothesis to validate; e.g., "Users prefer single-column layout to two-column in card list"]
- **SC-003**: [Business or research metric]

---

## Assumptions

<!--
  Things this spec assumes — revisit during /speckit.clarify.
  Mark any NEEDS CLARIFICATION explicitly.
-->

- [Assumption 1]
- [Assumption 2]

---

## Out of Scope

<!-- Explicit non-goals to keep the prototype focused. -->

- [Non-goal]
- [Non-goal]
