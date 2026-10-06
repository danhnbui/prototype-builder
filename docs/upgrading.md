# Upgrading Product Builder

A pb prototype has **three version layers that must stay coherent**. Most "the upgrade didn't take"
confusion is one layer moving without the others. This guide makes the layers explicit and gives the
one correct upgrade order.

> **Upgrading from any release?** Every release ships a migration guide in
> **[migrations/](migrations/README.md)** — the schema steps, retired commands and hand-written notes
> between the version you are on and that release. It is also attached to each GitHub Release as
> `MIGRATION-vX.Y.Z.md`.
>
> **Coming from 1.x?** 2.0 renamed twelve commands and deleted the old names. Start with
> **[upgrade-to-2.0.md](upgrade-to-2.0.md)** — the rename table plus the one command that moves your
> registry — then come back here if a layer still looks stale.

## The three layers

| # | Layer | What it is | Moves when |
|---|---|---|---|
| 1 | **Plugin code** | the shell template (`pb/template/prototype.html`) + `serve.py` + `render.py` | you install/upgrade the plugin via `/plugin` |
| 2 | **Registry** | `meta.schemaVersion` in `registry.json` | you run `/pb:update-version --apply` |
| 3 | **Rendered output** | `prototype.html` + the live `/pb:preview` | you re-render with the **current** plugin |

The trap: layer 1 can move while layer 3 stays stale — your prototype keeps showing the **old shell UI**
with no signal why. The rendered shell is **version-stamped** so this is visible:

- an in-page `pb vX.Y.Z` badge in the meta-nav (top-right),
- a `<!-- pb-shell vX.Y.Z · rendered <ISO> -->` comment near the top of `prototype.html`,
- a `· pb vX.Y.Z` line in the `/pb:preview` startup banner,
- a `⚠ Shell drift` warning from `/pb:test --drift` when the stamp is older than the installed plugin.

## Canonical upgrade sequence

1. **Upgrade the plugin** via `/plugin`. If a same-name marketplace collision blocks the new version:
   uninstall the old plugin → remove the old marketplace → add the desired source → install.
2. **Reload / restart the session** so the new command versions load.
3. **`/pb:update-version --apply`** to bring `registry.json` up to the current schema (run the default dry-run
   first to read the plan).
4. **Restart `/pb:preview`** so the live render uses the new shell. (A preview started inside a session
   that you then reload is killed with it — see the stability tip.)

After step 4, the meta-nav badge and the `/pb:test --drift` shell-coherence line should both report the
current version.

## Author dev-loop (editing the plugin itself)

- Edit plugin files → `/reload-plugins` to pick them up.
- Keep `plugin.json`'s `version` **stable** while iterating so reloads don't re-cache; bump it only on
  release. (The shell stamp tracks `plugin.json`, so a bump is how a release becomes visible.)
- Run `/pb:preview` from a **persistent terminal** (not one tied to a session you cycle) so the server
  survives reloads. Since v2.2 a preview stops itself after 30 minutes with no browser tab open and no
  request (`--idle-exit 0` keeps it running; `serve.py --status` / `--stop` inspect and end it).

## Symptom → layer → fix

| Symptom | Likely layer | Fix |
|---|---|---|
| New UI not showing in preview | 3 stale | Restart `/pb:preview`; or `/pb:build --render` then reload the page. |
| `⚠ Schema gap` banner on build | 2 behind 1 | `/pb:update-version --apply`. |
| `⚠ Shell drift` from `/pb:test --drift` | 3 behind 1 | Re-render (`/pb:build --render`) or restart `/pb:preview`. |
| `⚠ Shell unstamped` | 3 rendered by a plugin older than this feature | Re-render once with the current plugin. |
| Commands still behave like the old version | 1 not loaded | Reload/restart the session after `/plugin`. |
| Badge shows `pb vunknown` | `plugin.json` unreadable | Confirm `pb/.claude-plugin/plugin.json` has a string `version`. |
