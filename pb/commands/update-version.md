---
description: Run versioned schema updates on a Product Builder registry.json. Default is dry-run (prints the plan, writes nothing). Use --apply to execute, --rollback to restore the latest backup, --to <N> to target a specific schema version.
---

# /pb:update-version

Apply pending schema version updates to `registry.json`. **Default is dry-run — nothing is
written without `--apply`.**

## 0 · Flags
- (default) — dry-run: print the version-update plan and stop.
- `--apply` — run the chain in memory, back up, write once, re-render.
- `--rollback` — restore the latest `.pb-backups/` entry (the newest by modification time) and re-render. What is on disk now is saved to `.pb-backups/pre-rollback.<ts>/` first.
- `--to <N>` — target schema version (default: `CURRENT_SCHEMA` from `manifest.py`).
- `--registry <path>` — path to `registry.json` (default: `registry.json` in cwd).

## 1 · Run the update runner

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/migrations/migrate_runner.py" [flags passed by user]
```

Pass through any flags the user supplied. The runner handles all state, backup,
validation, and output. Read its printed output and surface it to the user.

## 2 · What the runner does (for reference)

**Dry-run (default):**
1. Reads `meta.schemaVersion` from `registry.json` (absent → treats as schema 2).
2. Reads `CURRENT_SCHEMA` from `pb/migrations/manifest.py`.
3. If equal: prints `✓ Already on schema N.` and stops.
4. Computes the version-update chain; prints each step's id + `describe()` text.
5. Prints `(Dry-run — nothing written. Pass --apply to execute.)` and stops.

**`--apply`:**
0. Takes the registry lock (`registry.json.lock`, the one every registry writer takes). If another pb process
   holds it past the timeout, the runner prints one line naming the holder and **exits 1** — nothing is
   touched. `--rollback` takes the same lock; dry-run takes none.
1. Backs up `registry.json` → `.pb-backups/registry.<from>.<ISO-ts>.json` (creates the dir), and snapshots
   `spec/components` + `spec/screens` beside it → `.pb-backups/spec.<from>.<ISO-ts>/` (a step may write
   sidecars — `0011` does).
2. Runs the `up()` chain — if any step fails, `registry.json` is untouched and the sidecars are put back.
3. Validates the result via `render.py`'s `build_html` — if this fails, nothing is written.
4. Writes `registry.json` once.
5. Re-renders `prototype.html`.
6. Prints a change summary and any `memory_notes()` as an advisory block.
   The advisory is **for the user to apply by hand** to `memory/constitution.md` — the
   runner NEVER writes to `constitution.md`, the Stack Lock, or the DS Lock.
7. On failure before the write: reports which step failed; `registry.json` is untouched and any sidecar a
   step rewrote is restored from its snapshot (files a step created are removed).
8. On failure after the write: restores `registry.json` **and** the sidecars from backup, then reports.
   (Other files a step writes — render bodies from `0002`, logic contracts from `0009` — are not snapshotted.)

**`--rollback`:**
1. Finds the latest `registry.*.json` in `.pb-backups/` — the **newest by modification time** (a same-second
   `-2` suffix does not sort by name).
2. **Snapshots the current state first** — `registry.json` and `spec/` as they are now →
   `.pb-backups/pre-rollback.<ts>/` — so edits made since the update stay recoverable, and says so. If that
   copy fails, nothing is restored.
3. Restores the backup to `registry.json`, and the matching `spec.<from>.<ts>/` snapshot to
   `spec/components` + `spec/screens` (a backup that predates sidecar snapshots leaves `spec/` as it is).
4. Re-renders `prototype.html`.
5. Confirms. **Backups are NEVER deleted** — a rollback adds one.

## NEVER
- NEVER write to `memory/constitution.md`, the Stack Lock, or the DS Lock.
- NEVER write without `--apply`.
- NEVER delete backups from `.pb-backups/` (a rollback adds a `pre-rollback.<ts>/` one).
- NEVER leave a half-updated registry — the chain runs fully in memory; one write at the end.
- NEVER run this command on behalf of another command — users invoke `/pb:update-version` explicitly.
