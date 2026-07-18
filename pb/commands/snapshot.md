---
description: Take a timestamped snapshot of registry.json (the pb history model) so a build session can roll back. Writes to <project>/history/. Never branches, never touches host git. --list to see them, --restore <snap> to roll back.
---

# /pb:snapshot

pb's history model (G-A = snapshot). Copies the current `registry.json` to a timestamped
file under `<project>/history/` — a cheap, isolated rollback point. It **never** creates a
git branch and **never** touches the host repo's git, which is exactly why snapshot (not an
orphan branch) is the model for adopt-in-place mode.

The history dir sits next to the registry: greenfield → `./history/`; adopt-in-place (run with
`.prototype/` as the project root) → `.prototype/history/` (already `.gitignore`d by `/pb:init`).

## Take a snapshot (default)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/snapshot.py" registry.json
```
Writes `history/registry.<UTC-timestamp>.json` and prints the path. Take one before a risky
structural edit or at the end of a good session.

## List snapshots (newest first)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/snapshot.py" registry.json --list
```

## Roll back
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/snapshot.py" registry.json --restore history/registry.<stamp>.json
```
Restores that snapshot over `registry.json`. It **auto-snapshots the current state first**, so a
restore is itself reversible. After restoring, run `/pb:build --render` (or `/pb:preview`) to
refresh the view.

## Notes
- Snapshots capture `registry.json` (the state). Render bodies under `render/` are edited
  directly and versioned by your normal git; a snapshot does not copy them.
- Nothing here writes outside the project's `history/` dir.
