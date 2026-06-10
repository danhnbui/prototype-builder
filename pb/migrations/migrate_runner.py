#!/usr/bin/env python3
"""
pb-migrate — versioned schema migration runner for Product Builder registry.json.

Usage (from the project root, or via /pb:migrate):
  python3 "${CLAUDE_PLUGIN_ROOT}/migrations/migrate_runner.py" [flags]

Flags:
  (default)          Dry-run: print the migration plan; write NOTHING.
  --apply            Run the chain in memory, back up, write once, re-render.
  --rollback         Restore the latest .pb-backups/ entry; re-render; confirm.
  --to <N>           Target schema version (default: CURRENT_SCHEMA from manifest.py).
  --registry <path>  Path to registry.json (default: registry.json in cwd).

NEVER list (enforced in code, not just docs):
  - Never auto-edit memory/constitution.md, the Stack Lock, or the DS Lock.
  - Never write without --apply.
  - Never delete a backup.
  - Apply runs the full chain in memory; writes registry.json exactly once at the end.
  - On failure before the write: nothing written; report the failing step.
  - On failure after the write: restore from backup; then report.
"""

import copy
import json
import os
import shutil
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_manifest():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "manifest", os.path.join(_HERE, "manifest.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_render():
    import importlib.util
    tools_path = os.path.abspath(os.path.join(_HERE, "..", "tools", "render.py"))
    spec = importlib.util.spec_from_file_location("render", tools_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _shell_path():
    return os.path.abspath(
        os.path.join(_HERE, "..", "template", "prototype.html")
    )


def _backup_dir(registry_path):
    return os.path.join(os.path.dirname(os.path.abspath(registry_path)), ".pb-backups")


def _latest_backup(registry_path):
    bdir = _backup_dir(registry_path)
    if not os.path.isdir(bdir):
        return None
    candidates = [
        os.path.join(bdir, f) for f in os.listdir(bdir)
        if f.startswith("registry.") and f.endswith(".json")
    ]
    if not candidates:
        return None
    # Sort by mtime: ISO timestamp names sort chronologically, but the same-second
    # collision suffix (-2, -3, …) breaks lexicographic order ('-' < '.'), so mtime
    # is the real "latest" signal. Name is the deterministic tiebreaker.
    candidates.sort(key=lambda p: (os.path.getmtime(p), p), reverse=True)
    return candidates[0]


def run(args=None):
    if args is None:
        args = sys.argv[1:]

    apply_mode = "--apply" in args
    rollback_mode = "--rollback" in args
    registry_path = "registry.json"
    to_v = None

    i = 0
    while i < len(args):
        if args[i] == "--registry" and i + 1 < len(args):
            registry_path = args[i + 1]
            i += 2
        elif args[i] == "--to" and i + 1 < len(args):
            to_v = int(args[i + 1])
            i += 2
        else:
            i += 1

    manifest = _load_manifest()
    CURRENT = manifest.CURRENT_SCHEMA

    # ── ROLLBACK ────────────────────────────────────────────────────────────────
    if rollback_mode:
        backup = _latest_backup(registry_path)
        if backup is None:
            print("✗ No backup found in .pb-backups/ — nothing to roll back.")
            sys.exit(1)
        shutil.copy2(backup, registry_path)
        print(f"✓ Restored from backup: {os.path.basename(backup)}")
        with open(registry_path) as f:
            reg = json.load(f)
        _rerender(reg, registry_path)
        print("✓ Rollback complete. Backups are preserved.")
        return

    # ── DRY-RUN / APPLY ─────────────────────────────────────────────────────────
    if not os.path.exists(registry_path):
        print(f"✗ Registry not found: {registry_path}")
        sys.exit(1)

    with open(registry_path) as f:
        reg = json.load(f)

    from_v = reg.get("meta", {}).get("schemaVersion", 2)  # unstamped → schema 2

    if to_v is None:
        to_v = CURRENT

    if from_v == to_v:
        print(f"✓ Already on schema {from_v}. Nothing to do.")
        return

    direction = "up" if to_v > from_v else "down"

    try:
        mods = manifest.chain(from_v, to_v)
    except ValueError as e:
        print(f"✗ {e}")
        sys.exit(1)

    print(f"Migration plan: schema {from_v} → {to_v} ({direction}, {len(mods)} step(s))")
    for mod in mods:
        stem = getattr(mod, "__name__", "?")
        print(f"  • {stem}: {mod.describe()}")

    if not apply_mode:
        print("\n(Dry-run — nothing written. Pass --apply to execute.)")
        return

    # ── APPLY ────────────────────────────────────────────────────────────────────

    # 1. Back up before touching anything
    bdir = _backup_dir(registry_path)
    os.makedirs(bdir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_name = f"registry.{from_v}.{ts}.json"
    backup_path = os.path.join(bdir, backup_name)
    # Second-granularity timestamps collide on a same-second re-apply. NEVER overwrite
    # an existing backup — append -2, -3, … until the name is unique (deterministic, stdlib).
    if os.path.exists(backup_path):
        n = 2
        while True:
            backup_name = f"registry.{from_v}.{ts}-{n}.json"
            backup_path = os.path.join(bdir, backup_name)
            if not os.path.exists(backup_path):
                break
            n += 1
    shutil.copy2(registry_path, backup_path)
    print(f"\n✓ Backed up → .pb-backups/{backup_name}")

    # 2. Run chain in memory
    working = copy.deepcopy(reg)
    for mod in mods:
        stem = getattr(mod, "__name__", "?")
        try:
            working = mod.up(working) if direction == "up" else mod.down(working)
        except Exception as e:
            print(f"✗ Migration failed at [{stem}]: {e}")
            print("  Nothing written (backup preserved).")
            sys.exit(1)

    # 3. Validate: result must parse and render.py must not error (pre-write)
    html = None
    shell = _shell_path()
    if os.path.exists(shell):
        try:
            render_mod = _load_render()
            with open(shell) as f:
                shell_src = f.read()
            html, _ = render_mod.build_html(working, shell_src)
        except Exception as e:
            print(f"✗ Pre-write render validation failed: {e}")
            print("  Nothing written (backup preserved).")
            sys.exit(1)

    # 4. Write registry.json exactly once
    try:
        with open(registry_path, "w") as f:
            json.dump(working, f, indent=2)
            f.write("\n")
    except Exception as e:
        print(f"✗ Write failed: {e}")
        print(f"  Restoring from backup {backup_name}...")
        shutil.copy2(backup_path, registry_path)
        sys.exit(1)

    # 5. Write prototype.html (post-write; restore on failure)
    if html is not None:
        project_dir = os.path.dirname(os.path.abspath(registry_path))
        out_path = os.path.join(project_dir, "prototype.html")
        try:
            with open(out_path, "w") as f:
                f.write(html)
            print("✓ prototype.html re-rendered.")
        except Exception as e:
            print(f"✗ Post-write render failed: {e}")
            print(f"  Restoring registry from {backup_name}...")
            shutil.copy2(backup_path, registry_path)
            sys.exit(1)

    # 6. Summary
    new_v = working.get("meta", {}).get("schemaVersion", to_v)
    print(f"✓ Migration complete: schema {from_v} → {new_v}")
    print(f"  registry.json updated · backup kept at .pb-backups/{backup_name}")

    # 7. Advisory memory_notes (NEVER auto-written)
    advisory = []
    for mod in mods:
        notes_fn = getattr(mod, "memory_notes", None)
        if callable(notes_fn):
            notes = notes_fn()
            if notes:
                stem = getattr(mod, "__name__", "?")
                advisory.append(f"  [{stem}]\n  {notes}")
    if advisory:
        print("\n── Advisory: apply these rule changes by hand to memory/constitution.md ──")
        for note in advisory:
            print(note)
        print("── (the migration engine NEVER writes to constitution.md) ──")


def _rerender(reg, registry_path):
    """Re-render prototype.html if the shell template exists."""
    shell = _shell_path()
    if not os.path.exists(shell):
        return
    project_dir = os.path.dirname(os.path.abspath(registry_path))
    out_path = os.path.join(project_dir, "prototype.html")
    try:
        render_mod = _load_render()
        with open(shell) as f:
            shell_src = f.read()
        html, _ = render_mod.build_html(reg, shell_src)
        with open(out_path, "w") as f:
            f.write(html)
        print("✓ prototype.html re-rendered.")
    except Exception as e:
        print(f"⚠ Re-render skipped: {e}")


if __name__ == "__main__":
    run()
