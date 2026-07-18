---
description: Browse the cloned design system — a storybook-style server that renders the token foundations as visual swatches plus the component catalog from the clone. The DS analogue of /pb:preview. Read-only; re-reads on every refresh.
---

# /pb:preview-ds

Serve a browsable reference of the **cloned** design system (from `/pb:pull-ds`): token
foundations as visual swatches (colors, space, radius, type, …) + the component catalog from
`design-system/<name>/.source.json`. Read-only — it never writes the registry or the clone.

## 1 · Preflight
- Confirm a DS has been cloned: `meta.dsSource` is set and `design-system/<name>/.source.json`
  exists. If not, tell the user to run `/pb:pull-ds` first and stop.

## 2 · Serve
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/ds_serve.py" registry.json [--name <ds>] [--port N] [--no-open]
```
- It re-reads `registry.json` + the clone snapshot on every request, so editing a token and
  refreshing shows the change — no rebuild step.
- `--name` selects which `design-system/<name>/` to show (defaults to `meta.designSystem.name`,
  else the first cloned DS). `--port` defaults to 5174 and auto-advances if busy.
- Leave it running in a terminal; stop with Ctrl-C.

## Notes
- This previews the **DS clone**, not the prototype — use `/pb:preview` for the prototype itself.
- Component cards show the clone's **metadata** (id · level · variants · purpose). A DS component
  becomes a live render only once it's built into the project as a component (via `/pb:build`).
- Never use this as a hand-off artifact — it's a local dev server.
