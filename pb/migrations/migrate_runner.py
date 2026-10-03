#!/usr/bin/env python3
"""
pb-migrate — versioned schema migration runner for Product Builder registry.json.

Usage (from the project root, or via /pb:update-version):
  python3 "${CLAUDE_PLUGIN_ROOT}/migrations/migrate_runner.py" [flags]

Flags:
  (default)          Dry-run: print the migration plan; write NOTHING.
  --apply            Run the chain in memory, back up, write once, re-render.
  --rollback         Restore the latest .pb-backups/ entry; re-render; confirm. The registry and
                     spec/ as they are NOW are first saved to .pb-backups/pre-rollback.<ts>/.
  --to <N>           Target schema version (default: CURRENT_SCHEMA from manifest.py).
  --registry <path>  Path to registry.json (default: registry.json in cwd).

NEVER list (enforced in code, not just docs):
  - Never auto-edit memory/constitution.md, the Stack Lock, or the DS Lock.
  - Never write without --apply.
  - Never delete a backup. (Rollback adds one: what it is about to overwrite.)
  - Apply runs the full chain; writes registry.json exactly once at the end.
  - On failure before the write: registry.json untouched; spec sidecars put back; report the step.
  - On failure after the write: restore registry.json AND the sidecars from backup; then report.

Sidecars. A migration may rewrite `spec/components/*.json` / `spec/screens/*.json` while the chain
runs (0011 does) — before the registry is written, so a failure used to leave them converted under
an unconverted registry. Apply therefore snapshots both directories next to the registry backup
(`.pb-backups/spec.<from>.<ts>/`, same suffix as `registry.<from>.<ts>.json`), and restores them —
files a migration created are removed — when the chain, the validation or either write fails, and on
`--rollback`. Other files a migration writes (render bodies from 0002, logic contracts from 0009)
are not snapshotted.

Concurrency. Apply and rollback hold `tools/slice.py`'s advisory lock (`registry.json.lock`) for
their whole run and write registry.json by temp file + `os.replace`; a second writer waits a few
seconds and is then refused with a message that names the holder. Dry-run takes no lock.
"""

import contextlib
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


_SLICE = None


def _slice():
    """tools/slice.py — the registry's write path: the advisory lock and the atomic write.
    Loaded by file path under another name, so it never shadows the builtin `slice`."""
    global _SLICE
    if _SLICE is None:
        import importlib.util
        path = os.path.abspath(os.path.join(_HERE, "..", "tools", "slice.py"))
        spec = importlib.util.spec_from_file_location("pb_slice", path)
        _SLICE = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_SLICE)
    return _SLICE


@contextlib.contextmanager
def _locked(registry_path, who):
    """The registry write lock for the body; a refusal is a one-line message and exit 1."""
    sl = _slice()
    try:
        with sl.registry_lock(registry_path, who):
            yield
    except sl.RegistryLocked as e:
        print(f"✗ {e}")
        sys.exit(1)


def _shell_path():
    return os.path.abspath(
        os.path.join(_HERE, "..", "template", "prototype.html")
    )


def _backup_dir(registry_path):
    return os.path.join(os.path.dirname(os.path.abspath(registry_path)), ".pb-backups")


# ── spec sidecar snapshots ──────────────────────────────────────────────────────────────
_SPEC_KINDS = ("components", "screens")


def _spec_snapshot_dir(bdir, backup_name):
    """registry.12.20260101T000000Z[-2].json → <bdir>/spec.12.20260101T000000Z[-2]/"""
    stem = backup_name[:-len(".json")] if backup_name.endswith(".json") else backup_name
    if stem.startswith("registry."):
        stem = stem[len("registry."):]
    return os.path.join(bdir, "spec." + stem)


def _spec_files(root):
    """{path relative to root: absolute path} for every .json under root/components and root/screens."""
    out = {}
    for kind in _SPEC_KINDS:
        for dirpath, _dirs, files in os.walk(os.path.join(root, kind)):
            for f in files:
                if f.endswith(".json"):
                    full = os.path.join(dirpath, f)
                    out[os.path.relpath(full, root)] = full
    return out


def _snapshot_specs(base_dir, snap_dir):
    """Copy spec/{components,screens}/**/*.json into snap_dir. The directory is created even when
    there is nothing to copy — its presence is what says 'there were none', so a restore knows to
    remove what a migration created. Returns the number of files."""
    root = os.path.join(base_dir, "spec")
    files = _spec_files(root)
    os.makedirs(snap_dir, exist_ok=True)
    for kind in _SPEC_KINDS:
        if os.path.isdir(os.path.join(root, kind)):
            os.makedirs(os.path.join(snap_dir, kind), exist_ok=True)
    for rel, full in files.items():
        dst = os.path.join(snap_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(full, dst)
    return len(files)


def _restore_specs(base_dir, snap_dir):
    """Make spec/{components,screens} hold exactly what snap_dir holds: changed files put back
    (atomically), files a migration created removed, directories it created removed when empty.
    Returns (restored, removed). Idempotent."""
    sl = _slice()
    root = os.path.join(base_dir, "spec")
    snap = _spec_files(snap_dir)
    restored = removed = 0
    for rel, full in _spec_files(root).items():
        if rel not in snap:
            os.remove(full)
            removed += 1
    for rel, src in snap.items():
        dst = os.path.join(root, rel)
        with open(src, "rb") as f:
            data = f.read()
        try:
            with open(dst, "rb") as f:
                if f.read() == data:
                    continue
        except FileNotFoundError:
            pass
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        sl.atomic_write_bytes(dst, data)
        restored += 1
    for kind in _SPEC_KINDS:                                    # prune what the migration made
        kdir = os.path.join(root, kind)
        if not os.path.isdir(kdir) or os.path.isdir(os.path.join(snap_dir, kind)):
            continue
        for dirpath, _dirs, _files in sorted(os.walk(kdir), key=lambda t: -len(t[0])):
            with contextlib.suppress(OSError):
                os.rmdir(dirpath)                               # only succeeds when empty
    if not any(os.path.isdir(os.path.join(snap_dir, k)) for k in _SPEC_KINDS):
        with contextlib.suppress(OSError):
            os.rmdir(root)                                      # spec/ itself was the migration's
    return restored, removed


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

    # ── ROLLBACK ────────────────────────────────────────────────────────────────
    if rollback_mode:
        backup = _latest_backup(registry_path)
        if backup is None:
            print("✗ No backup found in .pb-backups/ — nothing to roll back.")
            sys.exit(1)
        with _locked(registry_path, "update-version --rollback"):
            _rollback(registry_path, backup)
        return

    # ── DRY-RUN / APPLY ─────────────────────────────────────────────────────────
    if not os.path.exists(registry_path):
        print(f"✗ Registry not found: {registry_path}")
        sys.exit(1)
    if apply_mode:
        # The plan is read INSIDE the lock: another writer may have changed the registry since.
        with _locked(registry_path, "update-version --apply"):
            _plan_and_apply(registry_path, to_v, apply_mode=True)
    else:
        _plan_and_apply(registry_path, to_v, apply_mode=False)


def _pre_rollback_dir(bdir):
    """A fresh `.pb-backups/pre-rollback.<ts>/` path — never one that exists (a same-second second
    rollback gets -2, -3, …). Not `registry.*`, so `_latest_backup` never mistakes it for a backup."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(bdir, f"pre-rollback.{ts}")
    n = 2
    while os.path.exists(path):
        path = os.path.join(bdir, f"pre-rollback.{ts}-{n}")
        n += 1
    return path


def _snapshot_before_rollback(registry_path):
    """Save what is on disk NOW — registry.json and spec/{components,screens} — to
    `.pb-backups/pre-rollback.<ts>/` (registry.json + spec/…), before a rollback replaces it.

    A rollback restores the state from BEFORE the update, so everything edited after the update was
    applied is overwritten; this is how it stays recoverable. Returns (dir, n_spec_files). Raises
    OSError if the copy cannot be completed — the caller then stops before restoring anything."""
    base_dir = os.path.dirname(os.path.abspath(registry_path))
    pre = _pre_rollback_dir(_backup_dir(registry_path))
    os.makedirs(pre)
    if os.path.isfile(registry_path):
        shutil.copy2(registry_path, os.path.join(pre, "registry.json"))
    n_specs = _snapshot_specs(base_dir, os.path.join(pre, "spec"))
    return pre, n_specs


def _rollback(registry_path, backup):
    sl = _slice()
    with open(backup, "rb") as f:
        data = f.read()
    try:
        pre, n_specs = _snapshot_before_rollback(registry_path)
    except OSError as e:
        print(f"✗ Could not save the current registry.json before rolling back ({e}).")
        print("  Nothing restored — a rollback would overwrite edits made since the update.")
        sys.exit(1)
    print(f"✓ Saved the current registry.json"
          + (f" + {n_specs} spec sidecar(s)" if n_specs else "")
          + f" → .pb-backups/{os.path.basename(pre)}/ — edits made after the update are recoverable there.")
    sl.atomic_write_bytes(registry_path, data)
    print(f"✓ Restored from backup: {os.path.basename(backup)}")
    snap = _spec_snapshot_dir(os.path.dirname(backup), os.path.basename(backup))
    base_dir = os.path.dirname(os.path.abspath(registry_path))
    if os.path.isdir(snap):
        restored, removed = _restore_specs(base_dir, snap)
        print(f"✓ Restored spec sidecars from {os.path.basename(snap)}/ "
              f"({restored} put back, {removed} removed)")
    else:
        print("· No sidecar snapshot for this backup (it predates them) — spec/ left as it is.")
    with open(registry_path, encoding="utf-8") as f:
        reg = json.load(f)
    _rerender(reg, registry_path)
    print("✓ Rollback complete. Backups are preserved.")


def _plan_and_apply(registry_path, to_v, apply_mode):
    manifest = _load_manifest()
    CURRENT = manifest.CURRENT_SCHEMA

    with open(registry_path, encoding="utf-8") as f:
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

    print(f"Version update plan: schema {from_v} → {to_v} ({direction}, {len(mods)} step(s))")
    for mod in mods:
        stem = getattr(mod, "__name__", "?")
        print(f"  • {stem}: {mod.describe()}")

    if not apply_mode:
        print("\n(Dry-run — nothing written. Pass --apply to execute.)")
        return

    # ── APPLY ────────────────────────────────────────────────────────────────────
    sl = _slice()
    base_dir = os.path.dirname(os.path.abspath(registry_path))

    # 1. Back up before touching anything: the registry, and the spec sidecars a migration may rewrite
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
    snap_dir = _spec_snapshot_dir(bdir, backup_name)
    n_specs = _snapshot_specs(base_dir, snap_dir)
    print(f"\n✓ Backed up → .pb-backups/{backup_name}"
          + (f" (+ {n_specs} spec sidecar(s) → .pb-backups/{os.path.basename(snap_dir)}/)" if n_specs else ""))

    state = {"registry_written": False, "done": False}

    def fail(*lines):
        for line in lines:
            print(line)
        sys.exit(1)

    try:
        # 2. Run the chain (base_dir lets a migration read/write sidecar files, e.g. 0002 extracts
        #    render bodies to render/*.js next to the registry). The registry stays in memory; a
        #    sidecar a migration rewrites is put back by the `finally` below if anything fails.
        working = copy.deepcopy(reg)
        for mod in mods:
            stem = getattr(mod, "__name__", "?")
            try:
                working = mod.up(working, base_dir) if direction == "up" else mod.down(working, base_dir)
            except Exception as e:
                fail(f"✗ Version update failed at [{stem}]: {e}",
                     "  Nothing written (registry.json untouched, spec sidecars restored; backup preserved).")

        # 3. Validate: result must parse and render.py must not error (pre-write)
        html = None
        shell = _shell_path()
        if os.path.exists(shell):
            try:
                render_mod = _load_render()
                with open(shell, encoding="utf-8") as f:
                    shell_src = f.read()
                # Resolve any renderSrc bodies (v1.4) from disk before the pure build_html.
                resolved = render_mod.load_bodies(working, base_dir)
                html, _ = render_mod.build_html(resolved, shell_src)
            except Exception as e:
                fail(f"✗ Pre-write render validation failed: {e}",
                     "  Nothing written (registry.json untouched, spec sidecars restored; backup preserved).")

        # 4. Write registry.json exactly once — by temp file + os.replace, so it is the old file or the new one
        try:
            # ensure_ascii=False, deliberately. The default escapes every non-ASCII character to
            # \uXXXX, which on a project with non-English content rewrites EVERY line that has any
            # and inflates the file (measured: 900 KB -> 1.06 MB on a real registry, for a migration
            # that changed 126 keys). A version update must move what it says it moves and nothing
            # else, or a lossless rollback cannot be proven by diffing.
            state["registry_written"] = True      # from here the finally puts the backup back
            sl.atomic_write_text(registry_path, json.dumps(working, indent=2, ensure_ascii=False) + "\n")
        except Exception as e:
            fail(f"✗ Write failed: {e}",
                 f"  Restoring registry.json and the spec sidecars from {backup_name}...")

        # 5. Write prototype.html (post-write; restore on failure)
        if html is not None:
            out_path = os.path.join(base_dir, "prototype.html")
            try:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print("✓ prototype.html re-rendered.")
            except Exception as e:
                fail(f"✗ Post-write render failed: {e}",
                     f"  Restoring registry.json and the spec sidecars from {backup_name}...")
        state["done"] = True
    finally:
        if not state["done"]:                     # any failure, an interrupt included
            try:
                if state["registry_written"]:
                    with open(backup_path, "rb") as f:
                        sl.atomic_write_bytes(registry_path, f.read())
                _restore_specs(base_dir, snap_dir)
            except Exception as e:                # the backups are intact; say where, never hide it
                print(f"✗ Could not restore from the backup ({e}). "
                      f"Copy .pb-backups/{backup_name} over registry.json and "
                      f".pb-backups/{os.path.basename(snap_dir)}/ over spec/ by hand.")

    # 6. Summary
    new_v = working.get("meta", {}).get("schemaVersion", to_v)
    print(f"✓ Version update complete: schema {from_v} → {new_v}")
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
        print("── (the version-update engine NEVER writes to constitution.md) ──")


def _rerender(reg, registry_path):
    """Re-render prototype.html if the shell template exists."""
    shell = _shell_path()
    if not os.path.exists(shell):
        return
    project_dir = os.path.dirname(os.path.abspath(registry_path))
    out_path = os.path.join(project_dir, "prototype.html")
    try:
        render_mod = _load_render()
        with open(shell, encoding="utf-8") as f:
            shell_src = f.read()
        resolved = render_mod.load_bodies(reg, project_dir)
        html, _ = render_mod.build_html(resolved, shell_src)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print("✓ prototype.html re-rendered.")
    except Exception as e:
        print(f"⚠ Re-render skipped: {e}")


if __name__ == "__main__":
    run()
