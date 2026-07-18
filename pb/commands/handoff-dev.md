---
description: Hand off to engineering at a chosen tier — host (runnable single-file prototype), scaffold (deterministic React+Tailwind app), or hardened (idiomatic, DS-integrated, MCP-resolved, reviewed). Optional --component <id>. Records meta.outputTier + meta.exportTarget.
---

# /pb:handoff-dev

Hand the work to engineering at the **tier** that fits the need — cheapest first.

```
/pb:handoff-dev --tier=host | scaffold | hardened   [--component <id>]
```

## 0 · Contract gate (fail-closed — runs first, every tier)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/lint_registry.py" --strict registry.json
```
Non-zero (any `ERROR`) → **STOP**; print findings, tell the user to `/pb:build` and retry. Never
export from a registry that violates the contract (NS6).

## `--tier=host` (default) — the runnable prototype
Delegate to **`/pb:validate`**: render `prototype.html` and wrap it in a runnable Vite/Next reference
build. No component source — it serves the single file. Set `meta.outputTier = "host"`.

## `--tier=scaffold` — deterministic React + Tailwind
Invoke the **`design-component-export`** skill for the scaffold contract + honesty guardrails, then:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/render_react.py" registry.json --out handoff-dev/scaffold [--screen <id> | --component <id>]
```
Emits a self-contained React+Vite app: one wrapper component per registry component/screen (reusing
its render body), `tokens.css` (`:root` vars) + a token-mapped `tailwind.config.js`, and `npm run dev`
scaffolding. Deterministic; no MCP. Then set `meta.outputTier = "scaffold"`,
`meta.exportTarget = "react-tailwind"`, and tell the user: `cd handoff-dev/scaffold && npm install && npm run dev`.

> Honest scope (NS9): the scaffold is **mechanical** — wrappers around pb render bodies, styled by the
> DS tokens. It runs and lints clean; it is **not** idiomatic per-component JSX. That is the hardened tier.

## `--tier=hardened` — idiomatic, DS-integrated  ·  ⛔ NOT YET AVAILABLE
The hardened tier (idiomatic per-component Tailwind JSX, MCP-resolved against the real DS, repo-matched,
`validate_code`-scored, `pb-reviewer` + human approved) is **deferred** — it depends on:
- a resolved **G-B** decision (does the target repo adopt AntD or stay Tailwind-only → what code it maps to),
- the **`pb-full-picture.md`** export contracts, and
- the design-system MCP resolution path.

Until then, **STOP** and tell the user: hardened is not implemented; use `--tier=scaffold` for a runnable
React starting point, and provide the G-B answer + `pb-full-picture.md` to unlock hardening. Do **not**
fake an idiomatic export.

## NEVER
- NEVER export from a contract-violating registry (gate is fail-closed).
- NEVER present the scaffold as idiomatic/production JSX — it is a mechanical wrapper (NS9, honest claims).
- NEVER emit a hardened export until its inputs (G-B, `pb-full-picture.md`, MCP) exist.
