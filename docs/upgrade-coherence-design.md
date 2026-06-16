# Design — Upgrade Coherence (shell-drift detection + upgrade guide)

> Date: 2026-06-16 · Status: implemented 2026-06-16.
> Origin: a real upgrade (pb 1.3.1 → 1.4.1) where the plugin installed and the registry could be
> migrated, yet the rendered prototype kept showing the **old shell UI** with no signal why.

## Problem

A pb prototype has **three version layers that must stay coherent**, and today nothing makes layer 3
visible or checks it — so a stale render passes silently:

1. **Plugin code** — the shell template (`pb/template/prototype.html`) + `serve.py` + `render.py`. Moves on plugin install/upgrade.
2. **Registry** — `meta.schemaVersion` in `registry.json`. Moves on `/pb:migrate --apply`.
3. **Rendered output** — `prototype.html` + the live `/pb:preview`. Moves **only** when re-rendered by the *current* plugin.

The two observed symptoms map to this model:
- "the plugin version didn't fully migrate" → layers 1↔2 coordination (host-controlled `/plugin` + `/pb:migrate`).
- "the new UI didn't render in preview" → **layer 3 went stale silently** — the preview was served by an older `serve.py`/template and nothing said so.

## Goals

- Make the rendered shell's version **visible** wherever a prototype is served or produced.
- **Detect** when `prototype.html` is stale relative to the installed plugin, and warn (never block).
- Give users an **authoritative upgrade guide** that sequences the three layers correctly.

## Non-goals

- Automating Claude Code's `/plugin` install/upgrade — host-controlled, out of pb's reach.
- Comparing against Claude Code's internal `installed_plugins.json` — fragile coupling; rejected.
- Blocking any build/preview on drift — visibility + advisory only, matching the existing schema-gap banner philosophy.

## Design

### A · Shell version stamping (the missing signal)

`render.py` reads the plugin SemVer from `pb/.claude-plugin/plugin.json` (`version` field), located
relative to its own `__file__` (`../.claude-plugin/plugin.json`) — the same self-locating trick
`migrate_runner.py` uses. Fallback to `"unknown"` if not found. Because `serve.py` renders through the
same `build_html`, the live preview automatically carries the version of whatever `serve.py` is running.

The version is injected via a single placeholder the shell template exposes (e.g. `{{PB_SHELL_VERSION}}`),
filled by `build_html`. No hand-maintained marker — it tracks `plugin.json` on every render.

### B · Detection surfaces (all warn-only)

1. **Preview banner** — `serve.py` startup prints the rendering version, e.g. appends `· pb vX.Y.Z` to
   the existing `shell` line. (`serve.py` reads its own `plugin.json`.)
2. **In-page badge** — a small, unobtrusive `pb vX.Y.Z` element in the rendered shell (e.g. a corner of
   the meta-nav/footer), so the running version is visible in the browser.
3. **`prototype.html` stamp** — `render.py` writes `<!-- pb-shell vX.Y.Z · rendered <ISO-8601> -->` near
   the top of the output file.
4. **`/pb:check-drift` coherence check** — the existing read-only audit reads the `prototype.html` stamp,
   parses its version, and compares it to the current `plugin.json` version. On mismatch it emits a
   `WARN`:
   `⚠ Shell drift: prototype.html rendered by pb vX.Y.Z; current plugin is vA.B.C — re-render (/pb:build --render) or restart /pb:preview.`
   This is a step in the `/pb:check-drift` command body (it reads `prototype.html` + `plugin.json`); it is
   **not** added to `check.py`, which stays registry-focused.

### C · Upgrade guide — `docs/upgrading.md` (new)

- The **three-layer model** (above) as the mental model.
- The **canonical upgrade sequence**: (1) upgrade the plugin via `/plugin` (incl. resolving a same-name
  marketplace collision: uninstall → remove old marketplace → add the desired source → install); (2)
  **reload/restart the session** so commands load the new version; (3) `/pb:migrate --apply` to bring
  `registry.json` to the current schema; (4) **restart `/pb:preview`** so the live render uses the new shell.
- The **author dev-loop**: edit files → `/reload-plugins`; keep `plugin.json` `version` stable while
  iterating (so reload picks up edits without a re-cache); bump only on release.
- **Stability tip**: run `/pb:preview` from a **persistent terminal** session so the server survives —
  a server launched inside a cycling session gets killed with it.
- A **symptom → layer → fix** troubleshooting table.

## Affected files

| File | Change |
|---|---|
| `pb/tools/render.py` | Read `plugin.json` version; inject the page badge + write the `prototype.html` stamp comment. |
| `pb/tools/serve.py` | Append `pb vX.Y.Z` to the startup banner. |
| `pb/template/prototype.html` | Add a `{{PB_SHELL_VERSION}}` placeholder + a small version-badge element. |
| `pb/commands/check-drift.md` | Add the shell-coherence check step (read stamp vs `plugin.json`; warn). |
| `docs/upgrading.md` | New guide (section C). |
| `docs/migrations.md` | Remove "shell-drift detection" from the Phase 3–4 deferred non-goals. |
| `README.md` | Cross-link the upgrade guide. |

## Testing / acceptance

- Render with `render.py` → `prototype.html` contains `<!-- pb-shell vX.Y.Z · rendered … -->` and an
  in-page badge showing the version.
- `serve.py` banner shows `pb vX.Y.Z`.
- Hand-edit `prototype.html`'s stamp to an older version → `/pb:check-drift` emits the shell-drift `WARN`;
  matching version → no warning.
- A `plugin.json` with no/garbled version → stamp shows `unknown`, no crash.
- No build/preview is ever blocked by drift.

## Open implementation decisions (for the plan)

- Exact placement of the in-page badge (meta-nav corner vs. a page footer).
- Placeholder mechanism in `build_html` (token replace vs. a `PB_DATA` field consumed by the shell's adapter).
