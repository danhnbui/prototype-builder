# Changes from v0.4.0 → Product Builder v1.1.1

A **plumbing swap, not a rewrite**: the SpecKit machinery came out; the crown-jewel logic ported unchanged.

## New
- **`registry.json`** — the single source of truth the build loop edits (state moved out of the HTML).
- **Deterministic render generator** (`pb/tools/render.py`) — `registry.json` → `prototype.html`, ~0 model tokens (the batched-render lever).
- **Claude Code plugin** packaging — `pb@product-builder`; commands invoke as `/pb:*`.
- **`/pb:build-check-design-system`** — DS-first reuse / variant / build-local + the naming contract (was an inline gate inside v0.4.0 `build`).
- **Two-mode `/pb:hand-off`** — `--people` (view-only + auto cover) and `--context` (portable bundle for `/pb:init --import`).
- **`config` block** in the registry — `viewOnly`, `cover`, `iconCdn` (DS-agnostic icons).
- **Memory layer** — `memory/constitution.md` (Principles + Stack/DS locks) + `memory/decisions.md`.

## Renamed
- `scaffold` → **`/pb:init`**.
- `figma-push` → **`/pb:build-figma-handoff`** (DS-neutral — `dsMatch.library` from config, never HIVE).
- Tabs: `User Flow` → **UX Design**, `Design Handoff` → **UI Design**, `ERD` → **Data**.
- v0.4.0 `after_*`-hook Tab-2 sync → **folded into** the `init` / `specify` / `clarify` command bodies.

## Dropped
- **SpecKit entirely** — `extension.yml`, `preset.yml`, the `after_*` hooks, `sync-tab2`.
- `skills-refresh` (skills are referenced from `agent-skill-set`; no pinned-clone refresh).
- The single-file HTML monolith **as the edit target** (it's now a rendered view, regenerated from the registry).
- **HIVE hardcoding** — neutral tokens (`--neutral-*`, `--shadow-*`, `--radius-*`), a configurable icon source (default inline SVG), and a config-driven Figma match library.

## Ported unchanged (the crown jewels)
The `PB_DATA` render machinery, the inline drift gate, the 5-gate Figma push (G-FP0–G-FP5), the handoff
spec drawer (Anatomy · Specification · UI Logic · Usage), the wireflow, and the copy popover.

## Why it's cheaper
The G0.5 token spike (real tiktoken): isolated cosmetic tweaks are ~break-even, but **~3–5× cheaper over
a real build session** — the compact `registry.json` stays resident in context across the session while
the HTML monolith can't — plus a deterministic render that costs ~0 model tokens. Not the originally
assumed "17×": that figure assumed a naive monolith re-emitting large regions per tweak.
