---
name: craft-connect-flow
description: Connect multiple Product Builder screens into a working journey — navigation, shared state, entry/exit points, and transitions — using the shell's declarative data-* runtime. Use when building a multi-screen prototype or mapping its flow — loaded by /pb:build and /pb:sync-flow. Not for single-screen behavior (use think-logic) or arranging one screen's elements (use think-layout).
---

# craft-connect-flow

Make a set of screens feel like one app. In Product Builder the Prototype tab has **no screen-switcher** —
navigation is wired declaratively in render bodies via `data-*` attributes the shell's runtime handles.

## Navigation patterns
- **Link / button move** — `data-nav="<screen-id>"` navigates to that screen.
- **Submit then go** — `data-action="submit"` validates the form; on success `data-go="<screen-id>"`.
- **Auto-advance** — `data-redirect="<screen-id>"` + `data-redirect-ms="<n>"` (e.g. a success splash).
- **Feedback** — `data-toast="<msg>"` confirms an action without leaving the screen.
Every target id must be a real `screens[].id`.

## Entry & exit
- Name the **entry** screen (where the flow starts) and every **exit** (success, cancel, error).
- No dead ends: every screen has a way forward or back (loop-backs are fine).

## Shared state
- Prototype state is ephemeral (rebuilt from the registry each load) — don't rely on it persisting.
- Carry "state" by navigating to the screen that represents it (e.g. a `dashboard` after sign-in), not by
  trying to thread variables between bodies.

## Mapping to the UX Design tab
When documenting the journey (`/pb:sync-flow`), the same screens become nodes in the Mermaid wireflow:
single `Start`, ≥1 `End`, decisions end with `?`, branches labeled `-- Yes/No -->`. Keep the wireflow and
the wired `data-nav`/`data-go` targets in agreement.

## Output
The navigation map (which control on which screen goes where, via which attribute), entry/exit points, and
the wireflow node list. Hand per-screen validation to `think-logic`.

## Rules
- **Every nav target is a real screen id.** **No dead ends.** **Navigation is declarative** — data-* only.
