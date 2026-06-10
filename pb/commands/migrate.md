---
description: Run versioned schema migrations on a Product Builder registry.json. Default is dry-run (prints the plan, writes nothing). Use --apply to execute, --rollback to restore the latest backup, --to <N> to target a specific schema version.
---

# /pb:migrate

Apply pending schema migrations to `registry.json`. **Default is dry-run — nothing is
written without `--apply`.**

## 0 · Flags
- (default) — dry-run: print the migration plan and stop.
- `--apply` — run the chain in memory, back up, write once, re-render.
- `--rollback` — restore the latest `.pb-backups/` entry and re-render.
- `--to <N>` — target schema version (default: `CURRENT_SCHEMA` from `manifest.py`).
- `--registry <path>` — path to `registry.json` (default: `registry.json` in cwd).

## 1 · Run the migrate runner

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
4. Computes the migration chain; prints each step's id + `describe()` text.
5. Prints `(Dry-run — nothing written. Pass --apply to execute.)` and stops.

**`--apply`:**
1. Backs up `registry.json` → `.pb-backups/registry.<from>.<ISO-ts>.json` (creates the dir).
2. Runs the `up()` chain **in memory** — if any step fails, nothing is written.
3. Validates the result via `render.py`'s `build_html` — if this fails, nothing is written.
4. Writes `registry.json` once.
5. Re-renders `prototype.html`.
6. Prints a change summary and any `memory_notes()` as an advisory block.
   The advisory is **for the user to apply by hand** to `memory/constitution.md` — the
   runner NEVER writes to `constitution.md`, the Stack Lock, or the DS Lock.
7. On failure before the write: reports which step failed; nothing written.
8. On failure after the write: restores from backup, then reports.

**`--rollback`:**
1. Finds the latest file in `.pb-backups/` (lexicographic = newest ISO timestamp first).
2. Restores it to `registry.json`.
3. Re-renders `prototype.html`.
4. Confirms. **Backups are NEVER deleted.**

## NEVER
- NEVER write to `memory/constitution.md`, the Stack Lock, or the DS Lock.
- NEVER write without `--apply`.
- NEVER delete backups from `.pb-backups/`.
- NEVER leave a half-migrated registry — the chain runs fully in memory; one write at the end.
- NEVER run this command on behalf of another command — users invoke `/pb:migrate` explicitly.
