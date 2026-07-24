---
description: Open the design-system site — the /design-system route of the /pb:preview server, which live-renders THIS project's registry components (interactive demo + variant grid + push-to-figma + token foundations). One of the two sites projected from registry.json. Live-reloads on every registry/body/token edit.
---

# /pb:preview-ds

The **design-system site** — the component workbench, one of the two sites `/pb:preview` serves from
`registry.json` (the other is the prototype). It live-renders **this project's** components (not the
upstream clone): every component grouped by `scope` → atomic `level`, each **interactive** one with a
live demo, all with a variant grid, plus a Push-to-Figma bridge snippet and the token foundations.

## Serve
`/pb:preview` already serves it — the design system is the **`/design-system` route** of the same server:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/serve.py" registry.json      # then open  http://…/design-system
```
- Deterministic render via `render.build_ds()` (the SAME renderer `render.py --ds` uses) — `~0` model
  tokens, the token lever. The site inlines the registry + the shared `runtime.js` + the emitted
  `renderCmp*` bodies, so components render identically to the prototype (never duplicated).
- **Live-reload:** the server watches `registry.json` + `render/**/*.js` + the tokens and re-renders
  BOTH sites on any change. Editing a component and refreshing shows it immediately — no rebuild step.
- To write the site to disk (hand-off snapshot): `python3 render.py --ds registry.json design-system.html runtime.js design-system.out.html [ds-catalog.json]`.

## Notes
- **Interactive = auto-detected**: a component gets a live clickable demo if it declares a `state`
  property OR its body wires interaction (`data-action`/`data-nav`/`onclick`/`<button>`/`<input>`); others
  get the variant grid only. Confirm + declare `state` when you add interaction (see `/pb:build`).
- **Push to Figma** on a component emits its GHN DS Bridge node JSON — paste into the plugin's *Code →
  Figma* tab. Unresolved DS keys are honest gaps (resolve at `/pb:pull-ds` Scan DS), never invented.
- *(Retired: the old `ds_serve.py` browsed the upstream `.source.json` clone's metadata — superseded by
  this live, registry-driven site. The `.source.json` snapshot remains for `/pb:check-drift`.)*
