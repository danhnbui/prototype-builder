# Sandbox nav menu — design

*2026-07-18 · shell UI change (`pb/template/prototype.html`) · branch `feat/5-tab-ui`*

## Goal

Collapse the Prototype tab's scattered header tools (Browser/App chrome toggle, device switcher,
structure-tree toggle, sandbox ⋯ menu) **plus** the shell version into a **single `Sandbox ▾` button
at the right end of the meta nav bar**, present on all 5 tabs, that opens one context menu holding all
of it. Frees the per-tab header and gives one predictable home for sandbox controls.

## The button

- Label: literal **`Sandbox`** + a caret + a small live status dot, right-aligned at the end of the
  nav (`renderMetaNav`), on every tab.
- Reuses the shell's own button/popover styling — not a new visual language.

## The menu (adapts per tab)

**On the Prototype tab** — a `PREVIEW` group then a `SANDBOX` group:

- **Preview** (Prototype only): Chrome (`.proto-shell-toggle` Browser/App) · Device
  (`.proto-toolbar`/`.proto-device-btn` segmented tab group, active = soft token) · Structure tree (toggle).
- **Sandbox**: **Reset session** (top, neutral color) · **Roles** (dropdown of `meta.roles`) ·
  **Explore options** (dropdown; `/pb:explore` results) · **Terminal testing** (dropdown; `/pb:test`).
  - Roles / Explore / Terminal render **only when data exists**; otherwise the row is **disabled** (greyed).
- **Footer**: `pb v<version>`.

**On the other 4 tabs** — the `PREVIEW` group is omitted; the menu shows the `SANDBOX` group (as available)
+ the version footer + that tab's own action where relevant.

## Reuse (why it looks native)

Extend the existing `openSandboxMenu()` (already a `copy-popover` with the roles radiogroup + Reset and
Esc/backdrop/positioning). Add the preview controls by reusing the exact strings already built in
`renderPrototype()` (`shellToggle`, `switcher`, `structBtn`). No re-drawn controls, no new tokens.

## Edits

1. `renderMetaNav()` — append the `Sandbox ▾` button (calls `openSandboxMenu(this)`); remove the standalone
   `.meta-version` span (version moves into the menu footer).
2. `openSandboxMenu()` — rebuild its inner HTML into the adaptive menu above; disabled Roles/Explore/Terminal
   when their data is absent; dropdowns for those three.
3. `renderPrototype()` — remove `toolsFull` from the Prototype header CTA (the tools now live in the menu);
   keep the builders (`shellToggle`/`switcher`/`structBtn`) but feed them to the menu.

## Verification

- `tests/shell_lint.py` + the full suite stay green.
- Render the golden fixture → `localhost:5199`, screenshot each tab, confirm the button + menu + adaptation.
