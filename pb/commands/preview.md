---
description: Live preview dev server. Watches registry.json (+ the shell templates + runtime + render.py), re-renders through the same generator render.py uses, and live-reloads the browser on every change. One server, two routes from the one registry — the prototype at / and the design system at /design-system. In-memory by default; --write also writes both HTML files to disk.
---

# /pb:preview

A live preview of the build loop. The cheap loop (`/pb:build`) edits `registry.json` and
**stops without rendering** — this server closes the gap so you can *see* each edit: it watches
the registry, re-renders through the **same** deterministic generator (`render.py` → `build_html` /
`build_ds`, so the preview is byte-identical to `/pb:build --render`), and reloads the browser the
instant a watched file changes. Start it once, then run `/pb:build` (no `--render`) and watch it update.

**One server, two routes — both projected from the one `registry.json`:**
- **`/`** — the **prototype** (`prototype.html`): flows + screens, the 4 doc tabs.
- **`/design-system`** — the **design-system** site (`design-system.html`): every component as an
  interactive demo + variant grid + Push-to-Figma snippet, over the token foundations.

A header switcher links between them; a component/token edit re-renders **both**. Renders **in memory** —
it never hand-edits or clobbers either HTML file (router rule #1), serves on its own port, and never
writes back to `registry.json`. Both HTML files are derived hand-off snapshots, **never** a second
preview. View it in a normal **browser** (Chrome/Safari) at the printed URL — the server opens it for
you. (An in-app preview pane is optional; see the macOS note.)

## 0 · Flags
- `--port <N>` — bind a specific port (default: 8000, auto-incremented if busy).
- `--write` — *also* write **both** `prototype.html` and `design-system.html` to disk on every change
  (a watch-mode `/pb:build --render`). The written files are clean — the live-reload script is injected
  into the served pages only.
- `--no-open` — don't open the browser on start.
- `<registry.json>` — preview a registry other than `./registry.json`.

## 1 · Launch (from the project root, in the background)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/serve.py" registry.json
```
(In-place dev tree: `python3 pb/tools/serve.py registry.json`.) Start it as a **background** process —
it runs until stopped — then report the `preview http://…` URL from its startup banner. The server
opens that URL in your browser automatically unless `--no-open`.

## 2 · Iterate
Leave it running. Each `/pb:build` (no `--render` needed) re-renders and reloads every open tab.
A registry that won't render (invalid JSON mid-edit, a missing shell anchor) shows a recoverable
error page with the cause — fix and save, and it reloads clean.

## 3 · One canonical launcher entry (only if you use an in-app preview pane)
Viewing in a browser needs no `launch.json`. If you use an in-app **preview pane** (which reads
`.claude/launch.json`), keep exactly **one** entry per project. After `serve.py` prints its bound port,
register/refresh that single entry:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/preview_register.py" --port <bound-port> --project-dir .
```
It upserts one entry named `pb-preview · <folder>` (updates in place, never appends a duplicate),
collapses any duplicates for this project, and **never touches entries it doesn't own**. Run it on every
`/pb:preview` so the pane shows one preview, not a pile.

## Result
A watching dev server at `http://127.0.0.1:<port>/` (prototype) + `/design-system` (the component
workbench) that mirrors `registry.json` live on both routes, viewable in any browser. Stop it with
Ctrl-C (or by killing the background process).

## macOS note (in-app preview pane + ~/Desktop)
Viewing in a **browser always works**, wherever the project lives — the server reads `~/Desktop` fine
from a normal shell. The catch is only the **in-app preview pane**: Claude Code's preview-server sandbox
can't read TCC-protected folders (`~/Desktop`, `~/Documents`, `~/Downloads`) and does **not** inherit
Full Disk Access — a known, open bug
([claude-code#51312](https://github.com/anthropics/claude-code/issues/51312)); granting FDA does **not**
fix it. So to use the **pane** on a project under one of those folders, either keep the project
**outside** them (cleanest — the pane reads the real `registry.json`), or point the launcher at a
**staged, derived copy** outside them (`serve.py` + `render.py` + the shell + a *copy* of `registry.json`)
and treat that copy like `prototype.html`: generated, never hand-edited. `serve.py` already tolerates a
sandboxed working directory.

## NEVER
- NEVER hand-edit `prototype.html` to make the preview update — edit `registry.json` (router rule #1).
- NEVER add a second `pb-preview` entry for a project — `/pb:preview` upserts the one canonical entry.
- NEVER static-serve a project folder (`npx serve <dir>`) as "the preview" — that serves a possibly-stale
  `prototype.html` (the snapshot), not the live preview.
- NEVER use this as the hand-off artifact — it's a local dev server. Use `/pb:handoff-close` to share.
