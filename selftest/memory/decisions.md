# Decisions — Feedback widget

> The why-log. One entry per trade-off resolved, gate override, or lock change. Newest first.
> Appended automatically by `/pb:clarify` (UI Logic Trade-offs) and by the build loop on a
> drift-gate override.

<!-- Template entry — copy below this line:

## YYYY-MM-DD — <short title>
- **Decision:** <what was chosen>
- **Why:** <one or two lines>
- **Alternatives:** <what was rejected, and why not>
- **Affects:** <screens / components / tokens / logic>

-->

## 2026-06-06 — Figma hand-off must pass a render audit (G-FP6)
- **Decision:** Every Figma hand-off runs the full gated `/pb:build-figma-handoff`; the push is "done" only when the G-FP6 render audit passes (auto-layout · 0 absolute children · 0 raw values · variants in a ComponentSet · screen elements as instances). A failing invariant blocks the Step 7 contract write-back.
- **Why:** The quality jump from a quick manual sketch (Run 1) to the gated command (Run 2) came from the *process*, not the skill. A hard completion gate stops the manual shortcut from being mistaken for a real hand-off.
- **Alternatives:** Soft rule only (rejected — agent could skip it); hard runtime hook (rejected — breaks the v1.1.1 no-hooks architecture).
- **Affects:** components, screens, tokens — the whole hand-off

## 2026-06-05 \u2014 Required vs optional comment
- **Decision:** Optional
- **Why:** Required comments cut completion ~3\u00d7.
- **Alternatives:** Required (rejected)
- **Affects:** Prototype, UX Design
