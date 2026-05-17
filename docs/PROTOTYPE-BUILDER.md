# Prototype Builder

A reusable foundation for building **serious UX-test prototypes** in a single HTML file. Every prototype ships with its own documentation: objective, principles, user flow, component variants, and data model — all on doc tabs above the live app.

---

## What this is

`template.html` is a ready-to-fork single-file prototype with a 5-tab meta-navigation:

| # | Tab | What it shows | Audience |
|---|---|---|---|
| 1 | **Prototype** | The live, interactive app users actually test | Test participants, stakeholders |
| 2 | **Project Summary** | Objective, design principles, business rules | Design + product reviewers, future maintainers |
| 3 | **User Flow** | All states + transitions as a zoomable diagram | Designers, devs, QA |
| 4 | **Component Variants** | Custom organisms (non-design-system) with every variant | Devs implementing the design |
| 5 | **ERD** | Data model for a future production version | Backend devs, architects |

The pattern came out of the BDS Discovery prototype (see `../index.html` for a fully-filled-in example).

---

## When to use it

Use this template when **any** of the following are true:

- You're building a usability-test prototype that multiple people will review.
- The prototype will outlive the test (handoff to engineering, design reviews, retrospectives).
- You need to document business logic without spinning up a separate Notion/Confluence page.
- You want the documentation to live *with* the prototype so it never drifts.

**Don't use it when:**

- The prototype is a one-off throwaway for a single demo. (Use a Figma frame instead.)
- The work is a production app. (Use the React/Vite scaffold in `../bds-app/` as a reference instead.)

---

## Quick start

```bash
cp template.html my-prototype.html
open my-prototype.html        # or double-click in Finder
```

That's it. No `npm install`, no build step. Edit `my-prototype.html` in any text editor, refresh the browser to see changes.

To share: send the file, or drop it on GitHub Pages / Vercel / Netlify (static hosting).

---

## The 5 tabs in depth

### Tab 1 — Prototype

> **Function**: the live testable app. This is the main deliverable.

**Where to edit**: `renderPrototype()` near the top of the `<script>` block.

**What belongs here**: all the actual UI, state, and interactions of the prototype. Forms, buttons, navigation, animations, fake data — anything a test participant should see and touch.

**What does NOT belong here**: documentation, captions explaining how things work, side notes. Those go in the other 4 tabs.

**Quality criteria**:
- A first-time user can complete the primary task without instructions.
- All clickable elements actually respond (no dead buttons unless that's the test).
- Loading/empty/error states are handled.

---

### Tab 2 — Project Summary

> **Function**: the "why" behind the prototype.

**Where to edit**: `renderMetaSummary()`.

**Three sections, always in this order:**

1. **Objective** — *one paragraph*. What hypothesis is being tested? Who are the participants? What outcome would mean we're right?

2. **Principles** — *3 to 7 numbered rules*. Opinionated design principles that justify decisions across the whole prototype. Each is one sentence.
   > Examples: *"Segment-first — every stat adapts to the declared buyer persona."* / *"Compare as a deliberate task — max 3 items, persistent across navigation."*

3. **Key Logics & Rules** — *table*. Business rules driving the prototype's behaviour. Rule name on the left, detail on the right. Use `<code>` for function/symbol names.

**What does NOT belong here**: user flows (Tab 3), individual component specs (Tab 4), data shapes (Tab 5).

**Quality criteria**:
- A reviewer can describe what hypothesis is being tested after reading this tab alone.
- Every principle maps to at least one visible decision in the prototype.
- Every rule is testable — "if X, then Y" verifiable by clicking through the prototype.

---

### Tab 3 — User Flow

> **Function**: visual map of every state the prototype can be in and how the user moves between them.

**Where to edit**: `buildFlowSvg()` (the SVG generator). The canvas + legend layout in `renderMetaFlow()` is already set up.

**Visual language** (matches the legend on the right of the canvas):

| Shape | Color | Meaning |
|---|---|---|
| Black circle | `#1c1f22` | START / END terminal |
| Yellow diamond | `#F6C000` | Yes/No decision point |
| Blue rounded rectangle | `#4A90D9` | Screen or view |
| Green rounded rectangle | `#00A651` | Positive action / completion |
| Gray rectangle | `#E5E7EB` | Modal / secondary action |

**Connection labels** (badges on arrows):
- Green badge — affirmative branch (`Yes`, `Click card`, `Submit`)
- Red badge — negative branch (`No`, `Cancel`)
- Dark gray badge — neutral action (`Toggle`, `Switch`)

**What does NOT belong here**: the data model (Tab 5), individual screen specs (Tab 4).

**Quality criteria**:
- Every screen in the prototype appears at least once.
- Every decision diamond has both Yes and No branches drawn.
- Reaching `END` is possible from `START` along at least one path.

---

### Tab 4 — Component Variants

> **Function**: showcase of custom organisms (components NOT in your base design system), each rendered live in every variant.

**Where to edit**: `variantCtx` (state) + `renderMetaVariants()` (one section per component) + the component renderers themselves.

**What belongs here**: only **organism-level** components built for this prototype. A ProjectCard, a CompareBar, a custom HeroStats block, etc.

**What does NOT belong here**:
- Standard design-system components (Button, Input, Checkbox) — those are in the design system docs.
- Full screens or templates — those belong in the User Flow tab.
- Marketing slides or component "best practices" — keep this tab focused on actual variants.

**Pattern per component** (copy-paste this structure):

```html
<div class="variant-section">
  <div class="meta-h3">N · Component Name</div>
  <div class="variant-meta">One-line description.</div>
  <div class="variant-ctrls">
    <!-- chip toggles, one per variant -->
  </div>
  <div class="variant-preview">
    <!-- live render based on variantCtx[componentName] -->
  </div>
</div>
```

**Quality criteria**:
- Every custom organism has its own section.
- Every variant referenced in the prototype tab is selectable here.
- Toggling a variant updates the preview instantly (no page reload).

---

### Tab 5 — ERD (Entity Relationship Diagram)

> **Function**: data model that would power a production version. Shows entities, their fields, and how they relate.

**Where to edit**: the Mermaid `erDiagram` source inside `renderMetaERD()`.

**Notation**: Mermaid's ERD syntax. The legend on the right of the canvas explains the symbols (entity sample + 1:1 / 1:N / N:N cardinality).

**What belongs here**: entities, their key fields (with types and PK/FK markers), and relationships with cardinality.

**What does NOT belong here**:
- Frontend state shape — that's implicit in the prototype itself.
- API contracts — those belong in a separate API doc.
- DDL or implementation details — keep it conceptual.

**Quality criteria**:
- Every concept mentioned in the prototype is represented by an entity.
- Every entity has a PK field.
- Every FK field points at an existing entity in the diagram.

---

## Customising the design tokens

All design tokens live in the `:root` CSS block at the top of `template.html`. The most likely things you'll change:

```css
:root {
  --brand:         #1c4ed8;   /* primary accent  — your brand color */
  --brand-soft:    #eef2ff;   /* soft accent bg */
  --brand-strong:  #1e3aa3;   /* hover / pressed */

  --font-heading: 'Poppins', system-ui, sans-serif;
  --font-body:    'Inter',   system-ui, sans-serif;
}
```

Swap these three brand variables (and the `<link rel="stylesheet">` Google Fonts URL in the `<head>`) to match your design system. Everything else is on neutral grays.

---

## When to outgrow this template

The single-file approach starts hurting around **~3,000 lines**. Signs you should migrate:

- Hot-reload would save real time (current workflow: refresh manually).
- You want TypeScript / autocomplete / proper linting.
- You're copy-pasting components between prototypes.
- The prototype is becoming the production app.

When that happens, migrate to a Vite + React scaffold. See `../bds-app/` for an example of a partial migration from the single-file pattern.

---

## File map

```
prototype-builder/
├── template.html                  ← copy this, rename, edit
├── PROTOTYPE-BUILDER.md           ← this file (human guide)
└── .claude/
    └── skills/
        └── prototype-builder/
            ├── SKILL.md           ← Claude skill (agent guide)
            └── references/
                ├── tab-1-prototype.md
                ├── tab-2-summary.md
                ├── tab-3-user-flow.md
                ├── tab-4-variants.md
                └── tab-5-erd.md
```

For a fully-worked example, see the sibling `Project Hub/index.html` (the BDS Discovery prototype).
