#!/usr/bin/env python3
"""
snapshot.py — timestamped registry.json history for `/pb:snapshot` (v1.5.1).

The history model for pb (G-A = snapshot, not orphan-branch): point-in-time copies of
`registry.json` under `<project>/history/`, so a build session can roll back a bad
change. Pure stdlib (NS4). It **never** branches and **never** touches the host repo's
git — that is the whole reason snapshot was chosen over an orphan branch for
adopt-in-place mode.

The history dir is resolved next to the registry: `<dir-of-registry>/history/`. So in
greenfield that's `./history/`; run with `.prototype/` as the project root (adopt-in-place)
and it's `.prototype/history/` — the same path `/pb:init` adds to the host `.gitignore`.

Usage:
  python3 snapshot.py [registry.json]                     # take a snapshot
  python3 snapshot.py [registry.json] --list              # list snapshots, newest first
  python3 snapshot.py [registry.json] --restore <snap>    # restore a snapshot (snapshots current first)

Exit: 0 on success; non-zero with a message on error.
"""
import glob
import os
import shutil
import sys
from datetime import datetime, timezone


def _hist_dir(reg):
    return os.path.join(os.path.dirname(os.path.abspath(reg)), "history")


def _stamp():
    # Microsecond precision so a plain lexical sort of the filenames is chronological.
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")


def take(reg):
    if not os.path.isfile(reg):
        sys.exit(f"snapshot: no registry at {reg}")
    d = _hist_dir(reg)
    os.makedirs(d, exist_ok=True)
    stamp = _stamp()
    dst = os.path.join(d, f"registry.{stamp}.json")
    n = 1
    while os.path.exists(dst):  # astronomically unlikely; '_N' sorts AFTER '.json' so order holds
        dst = os.path.join(d, f"registry.{stamp}_{n}.json")
        n += 1
    shutil.copy2(reg, dst)
    print(f"✓ snapshot → {os.path.relpath(dst)}")
    return dst


def listing(reg):
    snaps = sorted(glob.glob(os.path.join(_hist_dir(reg), "registry.*.json")), reverse=True)
    if not snaps:
        print("(no snapshots yet)")
        return
    for s in snaps:
        print(os.path.relpath(s))


def restore(reg, snap):
    if not os.path.isfile(snap):
        sys.exit(f"snapshot: no such snapshot {snap}")
    if os.path.isfile(reg):
        take(reg)  # safety: capture the current state before overwriting it
    shutil.copy2(snap, reg)
    print(f"✓ restored {os.path.relpath(snap)} → {reg}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    reg, mode, snap, pos = "registry.json", "take", None, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--list":
            mode = "list"
        elif a == "--restore":
            mode = "restore"
            i += 1
            snap = argv[i] if i < len(argv) else None
        elif a.startswith("--"):
            sys.exit(f"snapshot: unknown flag {a}")
        else:
            pos.append(a)
        i += 1
    if pos:
        reg = pos[0]
    if mode == "take":
        take(reg)
    elif mode == "list":
        listing(reg)
    elif mode == "restore":
        if not snap:
            sys.exit("snapshot: --restore needs a snapshot path")
        restore(reg, snap)


if __name__ == "__main__":
    main()
