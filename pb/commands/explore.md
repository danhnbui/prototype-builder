---
description: Generate N alternative render bodies for one screen or component in parallel (default 3), preview each in isolation, and let the user pick — the chosen candidate is promoted over the real render body and the scratch candidates are deleted. Human-in-the-loop; registry.json stays untouched.
---

# /pb:explore <screen|component-id> [--options N]

Explore design alternatives for **one** target (a screen or component) without touching the registry.
Spawn N independent proposals, preview each, and let the **user** choose. Only the pick is promoted into
the real render body — everything else is thrown away. This is a **human-in-the-loop** divergence step; it
writes no registry slice (the registry stays clean) and never renders `prototype.html`.

## 0 · Flags & resolve the target
- `<screen|component-id>` — the **kebab-case id** to explore. Resolve it: is it a `screens[]` id or a
  `components[]` id? Record its `kind` (`screen` | `component`), its `renderFn`, and its real body path
  (`render/screens/<id>.js` or `render/components/<id>.js`). If the id doesn't exist, STOP and say so.
- `--options N` — how many alternatives to generate (**default 3**). Slots are `opt-1 … opt-N`.

## 1 · Diverge — N candidates in parallel
Launch **N `pb-builder` subagents** via the **Task tool**, concurrently (one message, N Task calls). Each
agent independently proposes a **full render body** for the target — a genuinely different take on layout /
emphasis / structure, but the **same `renderFn`** and the same public props as the target (so any candidate
is a drop-in). Each writes its body to a scratch slot:
```
render/_candidates/opt-<k>/<id>.js
```
Give every agent the target's current body (as a starting point to diverge from), its `renderFn`, its
props, and the one-line intent from `$ARGUMENTS`. Bodies are **token-only** (no raw hex/px — `lint_registry.py`).

## 2 · Preview each candidate in isolation
For each slot, render a standalone preview **on a temporary copy** of `registry.json` whose target entry's
`renderSrc` points at that candidate body (so the real registry is never edited):
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/render.py" <tmp-registry-opt-k.json> \
        "${CLAUDE_PLUGIN_ROOT}/template/prototype.html" render/_candidates/opt-<k>/preview.html
```
One `render.py` run per option. The result is `render/_candidates/opt-<k>/preview.html` — an openable,
self-contained preview of just that alternative.

## 3 · Record the options manifest
Write `memory/design-options.json` in the contract shape:
```json
{ "target": "<id>", "kind": "screen" | "component",
  "options": [
    { "slot": "opt-1", "label": "Option 1 — <one-line summary>",
      "renderSrc": "render/_candidates/opt-1/<id>.js", "renderFn": "<renderFn>" }
  ] }
```
One entry per generated slot; `label` is a short human-readable one-liner of that take.

## 4 · Present + let the user pick
Show the user the N options — each `label` plus the path to its `preview.html` to open — and **ask which to
keep** (or "none"). Do not decide for them; this step is human-in-the-loop.

## 5 · Promote the pick, discard the rest
On a pick:
1. Copy the chosen `render/_candidates/opt-<k>/<id>.js` over the **real** body
   (`render/screens/<id>.js` or `render/components/<id>.js`) — overwriting it in place. The registry's
   `renderFn` / `renderSrc` are unchanged (same names), so `registry.json` needs **no** edit.
2. Delete the whole `render/_candidates/` tree and `memory/design-options.json` (scratch only).
3. Tell the user to `/pb:build --render` (or rely on a running `/pb:preview`) to see the promoted body live.

On "none": delete `render/_candidates/` + `memory/design-options.json` and leave the real body untouched.

## NEVER
- NEVER edit `registry.json` — explore diverges bodies only; the registry stays clean.
- NEVER change a candidate's `renderFn` or props — every option must be a drop-in for the target.
- NEVER leave `render/_candidates/` behind after a decision — promote-then-delete, always.
- NEVER pick for the user — present the options and wait.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
