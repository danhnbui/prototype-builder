---
description: Generate or update Tab 1 (Prototype) and Tab 4-Component (Design Handoff component view) from the current spec, plan, and tasks. Runs an inline drift check against the constitution before any trio write. Honors Stack Lock and DS Lock.
handoffs:
  - label: Generate User Flow
    agent: speckit.prototype-builder.sync-flow
    prompt: Generate the user flow diagram for the prototype just built.
  - label: Generate Screen Handoff
    agent: speckit.prototype-builder.handoff
    prompt: Generate Tab 4-Screen handoff for the prototype just built.
---

## User Input

```text
$ARGUMENTS
```

If the user input is empty, build from the latest `.specify/specs/[active]/` artifacts. If user input specifies a story ID or screen name, scope the build accordingly.

## Inline Drift Check *(MUST run before any write to Tab 1, Tab 2, or Tab 4-C)*

This is the **trio drift check** — required because `/build` writes to all three live trio tabs. Custom commands have no SpecKit `before_*` hook, so the check lives here in the command body.

### Step A — Detect: does this build touch the trio?

`/build` always touches Tabs 1 and 4-C and may update Tab 2 (when new trade-offs surface). So **drift check is ALWAYS required for /build.** Skip the trio-touching detector — go straight to step B.

### Step B — Load principles

Read `.specify/memory/constitution.md`. Extract the **Principles** section (numbered list under `## Principles`). Cache the parsed principles for this session — do not re-read on subsequent /build calls in the same session.

If `constitution.md` is missing → HARD FAIL: `"Run /speckit.constitution first."`
If the Principles section is empty → WARN but proceed (no principles = no drift possible).

### Step C — Plan the proposed write

Synthesize a 1-paragraph summary of what `/build` is about to write to Tab 1 and Tab 4-C. Be specific about: components/organisms, layout decisions, state/logic introduced, and any new principles implied.

### Step D — Per-principle contradiction check

For each numbered principle, ask internally:

> "Does the proposed write contradict principle N?"

Collect every contradiction with its principle number and a one-line "because" reason.

### Step E — Branch on result

**If no contradictions** → proceed to "Write Tab 1 + Tab 4-C" below.

**If any contradictions** → output **exactly** this shape, then STOP:

```
⏸ DRIFT DETECTED

Proposed write:
  Tab 1: <summary>
  Tab 4-C: <summary>

Violates principle(s):
  #N — "<principle text>"
     because: <one-line reason>
  #M — "<principle text>"
     because: <one-line reason>

Approve override?  (yes / no / revise)
```

Wait for user prompt + Enter. Do NOT continue. Do NOT interpret silence as approval.

- On `yes` → proceed.
- On `revise` → stop, wait for the next prompt. Treat the next prompt as a fresh `/build` invocation.
- On `no` → stop, no write.

## Stack Lock Check *(G3)*

Read `.specify/memory/constitution.md` Stack Lock section. The chosen language + framework MUST match. If the proposed write deviates:

```
⏸ STACK SWITCH DETECTED

Constitution locks: <language>, <framework>
Proposed write uses: <attempted-language>, <attempted-framework>

Switch stack from X to Y?  (yes / no)
```

Wait for user response. Only proceed on `yes`. On `yes`, also update constitution.md Stack Lock and bump CONSTITUTION_VERSION.

## DS Lock Check *(G2)*

Inspect the proposed write for: inline `style="..."` attributes, external CSS imports, hex colors not in `./design-system/tokens.json`. Any violation:

```
⏸ DS OVERRIDE DETECTED

Locked DS: <source>
Offending styles:
  - <line>: <style>

Extend DS or override this once?  (extend / override / cancel)
```

- `extend` → user updates `./design-system/` to include the needed tokens; re-run build.
- `override` → proceed with the override BUT log it in `.specify/memory/ds-overrides.log`.
- `cancel` → stop, no write.

## Write Tab 1 + Tab 4-C

Once all gates pass:

### Tab 1 (Prototype)
- Source inputs: `spec.md` (user stories, edge cases), `plan.md` (per-story approach), `tasks.md` (implementation order), `./design-system/` (tokens + components).
- Invoke skills: `think-layout` for layout decisions, `think-logic` for state/rules.
- Write only inside the Tab 1 placeholder section of `./prototype/template.html`. Do not touch other tab markers.
- Use only DS tokens for colors, spacing, fonts. Use the locked language + framework.

### Tab 4-Component
- For each custom organism listed in `spec.md` "UI / Component Requirements" → "Custom Organisms":
  - Build the organism with all listed variants
  - Invoke skill: `design-component-build`
  - Add to Tab 4-C with variant chips + live preview
- For existing DS components used as-is: list them but do not rebuild

## Auto-sync Tab 2 (if new content surfaced)

If during build you surfaced a new trade-off or principle, append it to:
- New trade-off → `.specify/specs/[active]/clarify.md` UI Logic Trade-offs section (triggers `after_clarify` hook which writes Tab 2)
- New principle → `.specify/memory/constitution.md` Principles section (triggers `after_constitution` hook)

Do NOT write directly to Tab 2 — let the hook chain do it.

## Confirm to user

```
✅ Tab 1 (Prototype) and Tab 4-Component updated.

Drift check: passed (or: approved override)
Stack lock: honored
DS lock: <honored / N override(s) logged>

Decoupled tabs (3, 4-Screen, 5) may be stale. Run:
  /speckit.prototype-builder.sync-flow   if user flow changed
  /speckit.prototype-builder.handoff     if screens changed
  /speckit.prototype-builder.sync-erd    if data model changed
```

## Important rules

- **NEVER skip the inline drift check.** It is the whole point of /build.
- **NEVER auto-sync Tab 3, Tab 4-Screen, or Tab 5** from /build. Those tabs require their dedicated commands.
- **NEVER write code in Tab 4's Screen view right panel.** That's `/handoff`'s job and even there, code is forbidden.
- **NEVER bypass G2 or G3 by silently coercing styles or mixing stacks.**
- **NEVER invent new SpecKit commands or skill names.**
