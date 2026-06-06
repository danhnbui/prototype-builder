---
description: Live preview dev server. Watches registry.json (+ the shell template + render.py), re-renders through the same generator render.py uses, and live-reloads the browser on every change. In-memory by default; --write also updates prototype.html on disk.
---

# /pb:preview

A live preview of the build loop. The cheap loop (`/pb:build`) edits `registry.json` and
**stops without rendering** — this server closes the gap so you can *see* each edit: it watches
the registry, re-renders through the **same** deterministic generator (`render.py` → `build_html`,
so the preview is byte-identical to `/pb:build --render`), and reloads the browser the instant a
watched file changes. Start it once, then run `/pb:build` (no `--render`) and watch the page update.

Renders **in memory** — it never hand-edits or clobbers `prototype.html` (router rule #1). It serves
on its own port and never writes back to `registry.json`.

## 0 · Flags
- `--port <N>` — bind a specific port (default: 8000, auto-incremented if busy).
- `--write` — *also* write `prototype.html` to disk on every change (a watch-mode `/pb:build --render`).
  The written file is clean — the live-reload script is injected into the served page only.
- `--no-open` — don't open the browser on start.
- `<registry.json>` — preview a registry other than `./registry.json`.

## 1 · Launch (from the project root, in the background)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/serve.py" registry.json
```
(In-place dev tree: `python3 pb/tools/serve.py registry.json`.) Start it as a **background** process —
it runs until stopped — then report the `preview http://…` URL from its startup banner. The server
opens that URL automatically unless `--no-open`.

## 2 · Iterate
Leave it running. Each `/pb:build` (no `--render` needed) re-renders and reloads every open tab.
A registry that won't render (invalid JSON mid-edit, a missing shell anchor) shows a recoverable
error page with the cause — fix and save, and it reloads clean.

## Result
A watching dev server at `http://127.0.0.1:<port>/` that mirrors `registry.json` live. Stop it with
Ctrl-C (or by killing the background process).

## macOS note (preview panes / sandboxes)
Run by hand (`python3 …/serve.py`) it works anywhere. But a **sandboxed launcher** — e.g. an IDE/agent
"preview" pane that spawns the server — may be blocked by macOS **TCC** from reading files under
`~/Desktop`, `~/Documents`, or `~/Downloads` (`Operation not permitted`). If so: keep the project (or a
staged copy of `serve.py` + `render.py` + the shell + `registry.json`) **outside** those protected
folders and point the launcher there with absolute paths + `--shell`. The server itself already tolerates
a sandboxed/unreadable working directory.

## NEVER
- NEVER hand-edit `prototype.html` to make the preview update — edit `registry.json` (router rule #1).
- NEVER use this as the hand-off artifact — it's a local dev server. Use `/pb:hand-off` to share.
