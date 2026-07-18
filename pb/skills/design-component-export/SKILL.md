---
name: design-component-export
description: Export Product Builder components/screens to a deterministic React+Tailwind scaffold — the mechanical scaffold tier of /pb:handoff-dev. Use when emitting a runnable code starting point from the registry (no MCP, no repo integration). Produces React wrappers that reuse each render body + tokens.css + a token-mapped Tailwind theme. Not for idiomatic, DS-integrated per-component JSX (that is the hardened tier) or for building a component in the registry (use design-component-build).
---

# design-component-export

Emit the **scaffold** tier: a deterministic, runnable React+Vite app from the registry. This is the
cheap, faithful middle tier — above `host` (the single-file prototype), below `hardened` (idiomatic,
DS-integrated JSX). `pb/tools/render_react.py` does the writing; this skill is the contract + the
honesty guardrails.

## What the scaffold is (and is not)

- **Is:** one React component per registry component/screen, each a wrapper that renders that entity's
  own render body via `dangerouslySetInnerHTML`; the design tokens as `src/tokens.css` `:root` vars,
  also mapped into `tailwind.config.js` so utilities resolve to the tokens; `npm run dev` scaffolding.
  Deterministic (same registry → same output), self-contained, lints clean.
- **Is not:** idiomatic per-component Tailwind JSX. Render bodies are client-side JS; pb has no JS
  runtime to synthesize idiomatic markup deterministically. Rewriting a wrapper into hand-quality JSX,
  matched to a real repo and DS, is the **hardened** tier (`pb-hardener` + MCP + review).

## Rules

- **Deterministic only.** No timestamps, no randomness, no network in the emitted code — re-running is a
  no-op diff. (Provenance/timestamps belong in the registry, not the export.)
- **Faithful reuse.** Never rewrite or "improve" a render body during scaffold export — copy it verbatim
  as an ESM module. Fidelity is the scaffold's contract; improvement is the hardened tier's.
- **Tokens are the styling source.** Every color/space/radius/size is a token → a CSS var in `tokens.css`
  and a Tailwind theme entry. No raw hex/px introduced by the exporter.
- **Honest labeling (NS9).** The emitted `README.md` and any hand-off text must state the scaffold is
  mechanical (wrappers), not production JSX. Never let a scaffold be mistaken for the hardened tier.
- **Self-contained.** The output runs with `npm install && npm run dev` and nothing else — no reference
  back into the pb project.
