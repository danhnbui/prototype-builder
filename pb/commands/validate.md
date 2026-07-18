---
description: Wrap the rendered single-file prototype.html in a runnable reference build (Vite by default, or Next). Auto-renders prototype.html from registry.json first, then produces a buildable/runnable skeleton that serves that single file. This is a deployable reference, NOT a component-level code export — the artifact stays HTML.
---

# /pb:validate

Wrap the prototype in a **runnable reference build** — a deployable skeleton that serves the rendered
single-file `prototype.html`. This is the bridge from "open the file" to "host it like an app."

> **What this is — and isn't (NS9, honest claims).** The output **runs** the prototype (Vite/Next dev +
> build + preview); it is a thin wrapper around the single `prototype.html` file. It is **not** a
> component-level source export — there are no per-component `.jsx/.tsx` modules to import. The prototype
> artifact is **HTML regardless of the Stack Lock** (the Stack Lock records the *intended* production stack;
> it does not change what this command emits). A real JSX/TSX export is backlogged (see the playbook), gated
> on demonstrated engineering demand.

## 0 · Contract gate (fail-closed — runs first)
Before rendering or scaffolding, run the contract validator in **strict** mode:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/lint_registry.py" --strict registry.json
```
If it exits non-zero (any `ERROR`), **STOP** — do not render, do not scaffold. Print the
findings and tell the user to fix them (or run `/pb:build`) and retry. A scaffold must
never be built from a registry that violates the contract (NS6, fail-closed). Proceed
only on a clean exit (0).

## 1 · Render first
Run `/pb:build --render` so `prototype.html` is current with `registry.json`. (Never scaffold from a stale render.)

## 2 · Scaffold (Vite by default; `--next` for Next)
Create `validate/` (or `--out <dir>`):
- **Vite:** `package.json` (`vite` dev dep; scripts `dev`/`build`/`preview`), a minimal `vite.config.js`,
  and `index.html` = the rendered `prototype.html` copied in as the entry.
- **Next:** a Next app with the prototype as a static page + `package.json` scripts.

## 3 · Install + build
`npm install`, then `npm run build`. The build must exit 0 and `npm run preview` must serve the
prototype locally. Report the dev URL.

## Result
A buildable, runnable **reference** scaffold under `validate/` that serves the single-file prototype.

## NEVER
- NEVER scaffold from a stale `prototype.html` — `--render` first.
- NEVER claim success without an actual `npm run build` exit 0.
- NEVER describe the output as reusable component code or a production front-end — it serves the single-file
  HTML prototype (NS9). Engineers reuse the *design intent* (tokens, specs, flows), not these files as modules.
