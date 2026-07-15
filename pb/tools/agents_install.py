#!/usr/bin/env python3
"""
pb-agents-install — install the 8 pb-* subagents into a project's .claude/agents/.

Copies every `pb-*.md` shipped in this plugin's `pb/agents/` into
`<project-dir>/.claude/agents/`, creating the directory tree as needed. The upsert is
idempotent and owns only what it names:

  * OVERWRITES agent files named `pb-*.md` (the roster this plugin ships),
  * NEVER touches or deletes any file that does not match `pb-*.md` — hand-made agents,
    other tools' agents are left exactly as-is.

The source is resolved relative to THIS script (…/pb/tools → …/pb/agents), so it works both
from the in-place dev tree and from an installed plugin copy. Stdlib only — matching
preview_register.py / render.py and the project's no-deps stance.

Usage:  python3 agents_install.py [--project-dir <dir>]   (default project-dir = cwd)
"""
import argparse
import glob
import os
import sys
import tempfile

MARKER = "pb-"  # a file is plugin-owned iff its basename starts with this (and ends .md)


def _atomic_write(path, text):
    """Write text to path atomically (temp + os.replace), matching preview_register.py."""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.normpath(os.path.join(here, "..", "agents"))

    ap = argparse.ArgumentParser(
        prog="pb-agents-install",
        description="Install the pb-* subagents into <project-dir>/.claude/agents/.")
    ap.add_argument("--project-dir", default=".", help="project folder (default: cwd)")
    args = ap.parse_args()

    project_dir = os.path.realpath(args.project_dir)
    dest_dir = os.path.join(project_dir, ".claude", "agents")

    sources = sorted(glob.glob(os.path.join(src_dir, "pb-*.md")))
    if not sources:
        # Nothing to install (e.g. a stripped build). Not an error — succeed quietly.
        print(f"pb-agents-install: no pb-*.md agents found at {src_dir} — nothing to install.")
        sys.exit(0)

    wrote = unchanged = 0
    for src in sources:
        name = os.path.basename(src)  # already matches pb-*.md — the only files we own/write
        with open(src, encoding="utf-8") as f:
            text = f.read()
        dest = os.path.join(dest_dir, name)
        existing = None
        if os.path.isfile(dest):
            try:
                with open(dest, encoding="utf-8") as f:
                    existing = f.read()
            except OSError:
                existing = None
        if existing == text:
            unchanged += 1
            print(f"pb-agents-install: unchanged {dest}")
            continue
        _atomic_write(dest, text)
        wrote += 1
        print(f"pb-agents-install: wrote {dest}")

    print(f"pb-agents-install: {wrote} written, {unchanged} unchanged → {dest_dir} "
          f"(files not matching {MARKER}*.md left untouched)")
    sys.exit(0)


if __name__ == "__main__":
    main()
