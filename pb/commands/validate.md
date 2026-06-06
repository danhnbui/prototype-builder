---
description: Scaffold a real Vite or Next build from the prototype. Auto-renders prototype.html from registry.json first, then generates a buildable, runnable project skeleton.
---

# /pb:validate

Scaffold a real, runnable build from the prototype — the bridge from prototype → app.

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
A buildable, runnable scaffold under `validate/`.

## NEVER
- NEVER scaffold from a stale `prototype.html` — `--render` first.
- NEVER claim success without an actual `npm run build` exit 0.
