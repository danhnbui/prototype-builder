---
description: Live preview dev server. Watches registry.json (+ the shell templates + runtime + render.py), re-renders through the same generator render.py uses, and live-reloads the browser on every change. One server, two routes from the one registry — the prototype at / and the design system at /design-system — plus /explore/<id>, where /pb:explore's options are compared and rated on the same port. In-memory by default; --write also writes both HTML files to disk.
---

# /pb:preview

A live preview of the build loop. The cheap loop (`/pb:build`) edits `registry.json` and
**stops without rendering** — this server closes the gap so you can *see* each edit: it watches
the registry, re-renders through the **same** deterministic generator (`render.py` → `build_html` /
`build_ds`, so the preview is byte-identical to `/pb:build --render`), and reloads the browser the
instant a watched file changes. Start it once, then run `/pb:build` (no `--render`) and watch it update.

**One server, two routes — both projected from the one `registry.json`:**
- **`/`** — the **prototype** (`prototype.html`): flows + screens, the 4 doc tabs.
- **`/design-system`** — the **design-system** site (`design-system.html`): every component as a live
  demo (with Anatomy · Spec layers), variants & spec, anatomy and a Push-to-Figma action, beside the token
  foundations (one page per kind).
- **`/explore/<id>`** — while a `/pb:explore` is open: its options side by side, each rendered in memory
  with its candidate bodies swapped in (`/explore/<id>/<slot>` is one option alone), plus the rating panel
  (§2c). `/explore` lists the open explorations.

A header switcher links between them; a component/token edit re-renders **both**. Renders **in memory** —
it never hand-edits or clobbers either HTML file (router rule #1), serves on its own port, and never
writes back to `registry.json` — **except** the one thing you ask it to: the Project settings dialog's save
(`POST /api/meta`, §2d). Both HTML files are derived hand-off snapshots, **never** a second
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

## 2b · The `/design-system` route — the component workbench

The second route is the design-system site, and it is the same server: no second command, no second
process. Absorbs the former `/pb:preview-ds`, which existed only to say "open the other route".

It live-renders **this project's** components — never the upstream clone — grouped by `scope` → atomic
`level`, through `render.build_ds()`, the SAME renderer `render.py --ds` uses. It inlines the registry,
the shared `runtime.js` and the emitted `renderCmp*` bodies, so a component renders identically here and
in the prototype; nothing is duplicated. A component or token edit re-renders **both** routes.

- **Every listed component has a live demo.** The tree lists molecules, organisms and templates (plus a
  card-shaped atom, as a **Card**); an atom appears only as a part inside the component that uses it. Each
  listed component's Overview is a workbench — the clickable demo (the same `renderCmp*` the prototype
  uses), variant and device pickers, Layers (Anatomy · Spec: Margin / Padding / Gap, measured live), a Code
  view (HTML | CSS), *Edit props*, *Tokens used*, *Used in* — beside the **Variants & spec** and **Anatomy**
  tabs. A component whose behaviour hangs on a `state` property should still declare it (see `/pb:build`
  §3a): it is what puts the state in the variant picker.
- **Push to Figma** on a component is a dialog with two paths: **Copy JSON** (its DS Bridge node JSON,
  to paste into the plugin's *Code → Figma* tab) or **Copy prompt** (a prompt for Claude Code built on
  `/pb:handoff --mode=3 --scope=components --component <id>` and the project's Figma file). Unresolved DS
  keys are honest gaps — resolve them at `/pb:pull-ds` Scan DS, never invent one.
- **Token foundations are separate pages** — one per kind (Colour, Typography, Spacing, Radius,
  Elevation), as swatches, linked from **Foundations** in the tree (`#/f/<kind>`).
- **To disk** (a hand-off snapshot, not a preview): `--write` writes both files, or run
  `render.py --ds registry.json design-system.html runtime.js <out>.html [ds-catalog.json]`.

*(Retired with it: `ds_serve.py`, which browsed the upstream `.source.json` clone's metadata. This live,
registry-driven site superseded it. The `.source.json` snapshot stays — `/pb:test --drift` reads it.)*

## 2c · The `/explore/<id>` route — compare and rate

Same server, same port — an exploration never gets a server of its own. While
`memory/explore/<id>.json` is open (`explore.py init`), the server:

- renders each option **in memory** against the real registry with that slot's `overlay` swapped in
  (`render.load_bodies(..., overrides=…)`), so a candidate needs no temporary registry and no file on
  disk; saving a candidate body reloads its frame like any other body under `render/`;
- serves the compare page (`pb/template/explore-compare.html` with the manifest inlined): side by side or
  one at a time, the project's devices, each option's label / bet / axes, and the rubric × options grid;
- accepts `POST /__pb_explore/<id>/scores` from that page — **loopback and same-origin only** (the same
  three checks and the same body parsing as `POST /api/meta`, §2d, with a 1 MB limit), validated against the manifest's own
  rubric and slots, written atomically back to the manifest — so `explore.py gate` reads what the user rated;
- gives the live prototype a `window.PB_EXPLORE` summary, so **Sandbox → Explore** lists the options and
  jumps to one. The deep link `?screen=<id>&device=<id>&embed=1` opens any page of the shell on one
  screen without the tab bar.

- in a **page round** (`explore.py init --pages`), serves `memory/explore/<id>/<path>` as files at
  `/explore/<id>/<path>`, so an option page's relative links resolve. A bare `/explore/<id>/<slot>`
  redirects to that slot's `page`.

`promote` / `reject` archive the manifest, and the route and the Sandbox row go quiet again.

**Found by `explore.py link`.** On start the server writes `.preview/server.json` next to the
registry (url, port, pid, registry) and removes it on exit, Ctrl-C or SIGTERM. `GET /__pb_health`
(loopback only) names the registry it serves. `explore.py link <id>` reads the record and confirms
through the health route that the server is this project's. It starts one in the background if none
is, then prints `http://127.0.0.1:<port>/explore/<id>`: the URL every exploration hands the user.

## 2d · `POST /api/meta` — the Project settings save

The prototype and the design-system site share a **Project settings** dialog (project button in the bar):
project name · **design-system name (required)** · **Figma file (optional)** · theme. Served by this
server, **Save** posts `{ name, designSystem: { name, designLink } }` to `POST /api/meta`; opened over
`file://` the same dialog is **read-only** and hands out plain prompts to paste into Claude Code instead.

- **Writes exactly three fields** — `meta.name`, `meta.designSystem.name`, `meta.designSystem.designLink` —
  and nothing else (any other key is a 400). The rest of `meta` and of `meta.designSystem` (`codeLibrary`,
  `linked`, …) is kept; an emptied Figma link removes the key. The theme is **not** saved here: it is per
  viewer, in the browser. The registry file is rewritten **atomically** (temp file + `os.replace`) **under
  the registry lock** (`registry.json.lock`, below), then the watcher live-reloads every open page.
- **Loopback and same-origin only** — three checks, each a door: the peer address is loopback (not another
  machine on the LAN, when `--host` binds wider), the `Host` header names a loopback host (DNS rebinding),
  and `Origin` is this server itself (a cross-site page in the same browser). Any miss → **403**.
- **400** — a message the dialog shows beside the field, never a traceback: a missing / non-numeric /
  oversize `Content-Length` (limit 64 KB) or an incomplete body; not JSON, or nested too deeply; an
  unexpected field; `name` or `designSystem.name` empty (the DS name is required); a value containing a
  control, invisible (bidi / zero-width) or lone-surrogate character; a value over its length limit; a
  **changed** `designLink` that is not a `figma.com/file/…` or `figma.com/design/…` link.
- **A kept link is a warning, not an error.** A non-Figma link the project **already carries**, sent back
  unchanged, is kept and the response carries `warnings` — otherwise a project with such a link could never
  rename itself. The dialog shows the warning.
- **503** — another pb process holds the registry lock past the timeout (5s; `PB_LOCK_TIMEOUT`
  overrides): the message names the holder, and it clears by itself when that command ends. **500** — an
  unreadable or unwritable `registry.json`, or something that is not a regular file sitting where the lock
  goes.
- **The registry lock.** `registry.json.lock` is an advisory `fcntl.flock` taken by **every** writer of
  `registry.json` — this endpoint, `slice.py`, `spec_measure.py --write`, the migration runner,
  `logic_extract.py`, `lint_registry.py --sync-elements`, `resolve_frame.py`, `clone_ds.py`, `/pb:test`'s
  `lastResult` save and `/pb:explore`'s IA promote — so two of them never lose each other's edit. The
  kernel drops it when its process exits, so a crashed writer never leaves a stale lock. It is a local
  file: it is git-ignored.

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
workbench) that mirrors `registry.json` live on both routes, viewable in any browser, and takes the
Project settings save (`POST /api/meta`). Stop it with
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
- NEVER use this as the hand-off artifact — it's a local dev server. Use `/pb:handoff` to share.
- NEVER start a second server (or `python3 -m http.server`) to show explore options — they live at
  `/explore/<id>` on this one.
