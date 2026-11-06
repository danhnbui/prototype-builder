#!/usr/bin/env python3
"""
decisions_rotate.py — keep `memory/decisions.md` small enough to read (D-21·4).

The why-log only grows. A real project reached **187 entries / 875 KB in two months**, which is
the file three commands append to and — since v2.0.0 — grep before appending. Past a point the
current decisions are buried under the historical ones.

  Size, never the calendar. That same project wrote 86 entries in 2026-07 and 100 in 2026-08:
  a year rule would never have fired on the log that needed it most. The threshold is 500 KB.

  Whole entries, by their own date, never by position. That log is NOT in date order — it runs
  22 August entries, then 86 July ones, then 78 more August. Rotating "the tail" would archive
  recent entries and keep old ones. An entry whose heading carries no date is never moved: not
  being able to date something is a reason to leave it alone.

  Lossless or nothing. The original is backed up, the split is written, and then everything is
  read back and compared entry for entry against what was there before. A mismatch restores the
  backup and exits 2. This tool moves someone's history; it does not get to be approximately right.

Readers must glob `decisions*.md`. `/pb:handoff` already does (its bundle would otherwise
ship a history that stops at the first rotation, silently).

  decisions_rotate.py <memory/decisions.md>            # dry run: what would move, and where
  decisions_rotate.py <memory/decisions.md> --apply
  decisions_rotate.py <memory/decisions.md> --threshold-kb 250 --apply

One rotation at a time: `memory/.decisions.lock` (O_CREAT|O_EXCL, stale after 10 minutes) is held
while --apply runs; a second run prints one line, changes nothing and exits 0. Before it writes, the
live file is checked again (size, mtime, content): an entry appended since it was read aborts the run
with nothing moved, so an append is never lost.

Exit: 0 = clean (or nothing to do, or busy) · 2 = aborted, nothing changed.
"""
import argparse
import datetime
import os
import re
import shutil
import sys
import time

DEFAULT_THRESHOLD_KB = 500
LOCK_NAME = ".decisions.lock"      # next to decisions.md; O_CREAT|O_EXCL, so two rotations never overlap
LOCK_STALE_S = 600                 # a lock older than this belongs to a dead run: remove it and retake
BUSY = "busy"                      # rotate()'s return when the lock is held: nothing was changed
_HEADING = re.compile(r"(?m)^## .*$")
_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def split_entries(text):
    """(preamble, [(heading, body_including_heading), …]) — entries start at a column-0 `## `.

    Everything before the first heading is the preamble: the title, the house-format note, the
    commented-out template. It stays with the live file, because a sibling nobody writes to does
    not need instructions for writing to it — but it is re-emitted at the top of each sibling as
    a one-line pointer so a reader who opens one knows where it came from.
    """
    marks = [m.start() for m in _HEADING.finditer(text)]
    if not marks:
        return text, []
    preamble = text[:marks[0]]
    bounds = marks + [len(text)]
    return preamble, [text[bounds[i]:bounds[i + 1]] for i in range(len(marks))]


def entry_year(entry):
    """The year in the entry's heading, or None. Only the heading — a date inside the body is
    about the thing decided, not about when it was decided."""
    m = _DATE.search(entry.split("\n", 1)[0])
    return m.group(1) if m else None


def entry_key(entry):
    m = _DATE.search(entry.split("\n", 1)[0])
    return m.group(0) if m else ""


def plan(text, threshold):
    """(keep, move) — the newest datable entries that fit under `threshold`, and the rest.

    Ordering inside each list is the FILE's order, not date order: rotation is not a reason to
    reshuffle a log someone reads top to bottom.
    """
    preamble, entries = split_entries(text)
    if not entries or len(text.encode("utf-8")) <= threshold:
        return entries, []
    undated = {i for i, e in enumerate(entries) if entry_year(e) is None}
    # Newest first by date; an undated entry is pinned and never counts against the budget.
    ranked = sorted((i for i in range(len(entries)) if i not in undated),
                    key=lambda i: entry_key(entries[i]), reverse=True)
    budget = threshold - len(preamble.encode("utf-8"))
    for i in undated:
        budget -= len(entries[i].encode("utf-8"))
    keep_idx = set(undated)
    for i in ranked:
        size = len(entries[i].encode("utf-8"))
        if budget - size < 0:
            break
        budget -= size
        keep_idx.add(i)
    keep = [e for i, e in enumerate(entries) if i in keep_idx]
    move = [e for i, e in enumerate(entries) if i not in keep_idx]
    return keep, move


def sibling_note(year, source):
    return ("# Decisions — archived %s\n\n"
            "> Rotated out of `%s` by size. Still part of the log: anything reading it must glob\n"
            "> `decisions*.md`. Newest first, in the order they were written.\n\n" % (year, source))


def lock_path(path):
    return os.path.join(os.path.dirname(os.path.abspath(path)), LOCK_NAME)


def lock_is_fresh(path):
    """True when `path`'s directory holds a rotation lock younger than LOCK_STALE_S. Callers that
    would start a rotation (the housekeeping hook) use this to stay out of the way."""
    try:
        return time.time() - os.lstat(lock_path(path)).st_mtime <= LOCK_STALE_S
    except OSError:
        return False


def _take_lock(lock):
    """Create the lock with O_CREAT|O_EXCL → True when we hold it, False when someone else does,
    None when the directory will not let us create it. A lock older than LOCK_STALE_S is a dead
    run's: remove it once and take it again."""
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                age = time.time() - os.lstat(lock).st_mtime
            except OSError:
                continue                  # it vanished between the two calls: try to take it again
            if age <= LOCK_STALE_S:
                return False
            try:
                os.remove(lock)
            except OSError:
                return False
            continue
        except OSError:
            return None
        try:
            os.write(fd, ("%d %s\n" % (os.getpid(), datetime.datetime.now(datetime.timezone.utc)
                                       .strftime("%Y-%m-%dT%H:%M:%SZ"))).encode("ascii"))
        finally:
            os.close(fd)
        return True
    return False


def _release_lock(lock):
    try:
        os.remove(lock)
    except OSError:
        pass


def _unused(dst):
    """`dst`, or `dst` with .1, .2 … before the extension when that name is taken (two runs in the
    same second, or a read-only backup copied from a read-only file, must never collide)."""
    if not os.path.lexists(dst):
        return dst
    root, ext = os.path.splitext(dst)
    n = 1
    while os.path.lexists("%s.%d%s" % (root, n, ext)):
        n += 1
    return "%s.%d%s" % (root, n, ext)


def _stamp(f):
    st = os.fstat(f.fileno())
    return (st.st_size, st.st_mtime_ns)


def _stat_stamp(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


def _analyse(path, threshold):
    """Read the live file and its siblings once → everything the plan and the verification need."""
    with open(path, encoding="utf-8") as f:
        original = f.read()
        stamp = _stamp(f)
    preamble, live_entries = split_entries(original)
    base = os.path.dirname(os.path.abspath(path))
    name = os.path.splitext(os.path.basename(path))[0]
    # The invariant is about the whole `decisions*.md` FAMILY, not this one file. A second
    # rotation appends to a sibling that already holds history; comparing the live file's
    # entries against the family afterwards reports every previously-archived entry as an
    # extra, and the abort path then "rolls back" history it never wrote.
    family_before = list(live_entries)
    for sib in sorted(_siblings(base, name)):
        with open(sib, encoding="utf-8") as f:
            family_before += split_entries(f.read())[1]
    keep, move = plan(original, threshold)
    by_year = {}
    for e in move:
        by_year.setdefault(entry_year(e) or "undated", []).append(e)
    return {"original": original, "stamp": stamp, "preamble": preamble, "live_entries": live_entries,
            "family_before": family_before, "keep": keep, "move": move, "by_year": by_year,
            "base": base, "name": name}


def _announce(path, info, threshold):
    size_kb = len(info["original"].encode("utf-8")) / 1024
    kept_bytes = len((info["preamble"] + "".join(info["keep"])).encode("utf-8"))
    print("decisions_rotate: %s — %.0f KB / %d entries, threshold %.0f KB"
          % (os.path.basename(path), size_kb, len(info["live_entries"]), threshold / 1024))
    print("  keep  %3d entries  (%.0f KB)" % (len(info["keep"]), kept_bytes / 1024))
    for year in sorted(info["by_year"]):
        chunk = info["by_year"][year]
        print("  move  %3d entries  (%.0f KB)  -> %s-%s.md"
              % (len(chunk), sum(len(e.encode("utf-8")) for e in chunk) / 1024, info["name"], year))


def rotate(path, threshold, apply_=False):
    """0 = done or nothing to do · 2 = aborted, nothing changed · BUSY = another rotation holds the lock."""
    info = _analyse(path, threshold)
    if not info["move"]:
        print("decisions_rotate: %s is %.0f KB / %d entries — under the %.0f KB threshold, nothing to do"
              % (os.path.basename(path), len(info["original"].encode("utf-8")) / 1024,
                 len(info["live_entries"]), threshold / 1024))
        return 0
    if not apply_:
        _announce(path, info, threshold)
        print("\n(Dry run — nothing written. Pass --apply.)")
        return 0

    lock = lock_path(path)
    got = _take_lock(lock)
    if got is False:
        print("decisions_rotate: busy — another rotation holds %s (stale after %d min); nothing changed"
              % (LOCK_NAME, LOCK_STALE_S // 60))
        return BUSY
    if got is None:
        print("decisions_rotate: cannot create %s in %s — nothing changed" % (LOCK_NAME, info["base"]))
        return 2
    try:
        # Everything above was read without the lock: read it again now that nobody else can be
        # rotating, and plan from that.
        info = _analyse(path, threshold)
        if not info["move"]:
            print("decisions_rotate: %s is under the %.0f KB threshold now — nothing to do"
                  % (os.path.basename(path), threshold / 1024))
            return 0
        _announce(path, info, threshold)
        return _apply(path, info)
    finally:
        _release_lock(lock)


def _apply(path, info):
    original, preamble, keep = info["original"], info["preamble"], info["keep"]
    family_before, by_year = info["family_before"], info["by_year"]
    base, name = info["base"], info["name"]

    bdir = os.path.join(base, ".pb-backups")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    saved = {}                               # sibling path -> its backup, for siblings that existed
    try:
        os.makedirs(bdir, exist_ok=True)
        backup = _unused(os.path.join(bdir, "%s.%s.md" % (name, stamp)))
        shutil.copy2(path, backup)
        # Back up EVERY file this run will touch, not just the live one. A sibling that already
        # holds archived entries is history too, and the rollback must put it back as it was —
        # an earlier version deleted it instead, losing 98 entries it had never written.
        for year in by_year:
            sib = os.path.join(base, "%s-%s.md" % (name, year))
            if os.path.isfile(sib):
                sib_backup = _unused(os.path.join(bdir, "%s-%s.%s.md" % (name, year, stamp)))
                shutil.copy2(sib, sib_backup)
                saved[sib] = sib_backup
    except OSError as e:
        print("decisions_rotate: could not take the backups (%s) — nothing moved" % e)
        return 2

    touched = []                             # siblings this run opened for writing (so may have changed)
    live_touched = []

    def _restore():
        """Put back what this run changed: the live file only if it was opened for writing, each
        sibling only if it was opened for writing (a refused open changed nothing), and delete only
        a sibling this run created. Never raises: it says what it could not put back."""
        failed = []
        if live_touched:
            try:
                shutil.copy2(backup, path)
            except OSError as e:
                failed.append("%s (%s)" % (path, e))
        for target in touched:
            try:
                if target in saved:
                    shutil.copy2(saved[target], target)
                else:
                    os.remove(target)        # only files this run CREATED
            except OSError as e:
                failed.append("%s (%s)" % (target, e))
        if failed:
            print("decisions_rotate: COULD NOT RESTORE %s — the originals are in %s"
                  % ("; ".join(failed), os.path.relpath(bdir, base)))

    def _live_unchanged():
        if _stat_stamp(path) != info["stamp"]:
            return False
        try:
            with open(path, encoding="utf-8") as f:
                return f.read() == original
        except (OSError, ValueError):
            return False

    def _changed():
        print("decisions_rotate: %s changed while it was being rotated (an entry was probably appended) "
              "— nothing moved; run it again" % os.path.basename(path))
        return 2

    # The copy above is of what we planned from only if nothing wrote in between.
    if not _live_unchanged():
        return _changed()

    try:
        for year, chunk in sorted(by_year.items()):
            sib = os.path.join(base, "%s-%s.md" % (name, year))
            if os.path.isfile(sib):
                with open(sib, encoding="utf-8") as f:
                    existing = split_entries(f.read())[1]
                chunk = existing + [e for e in chunk if e not in existing]
            with open(sib, "w", encoding="utf-8") as f:
                touched.append(sib)
                f.write(sibling_note(year, os.path.basename(path)) + "".join(chunk))
        # Last look before the only write that removes anything from the live file.
        if not _live_unchanged():
            _restore()
            return _changed()
        with open(path, "w", encoding="utf-8") as f:
            live_touched.append(path)
            f.write(preamble + "".join(keep))
    except OSError as e:
        _restore()
        print("decisions_rotate: write failed (%s) — restored from the backup, nothing moved" % e)
        return 2

    # ── the assertion this tool exists for ────────────────────────────────────
    after = []
    with open(path, encoding="utf-8") as f:
        after += split_entries(f.read())[1]
    for sib in sorted(_siblings(base, name)):
        with open(sib, encoding="utf-8") as f:
            after += split_entries(f.read())[1]
    if sorted(after) != sorted(family_before):
        _restore()
        print("decisions_rotate: ABORTED — %d entries across decisions*.md before, %d after. "
              "Restored every file from %s; nothing moved."
              % (len(family_before), len(after), os.path.relpath(bdir, base)))
        return 2

    print("\n✓ rotated, verified lossless: %d entries across decisions*.md before, %d after, "
          "every one byte-identical" % (len(family_before), len(after)))
    print("  backup  %s" % os.path.relpath(backup, base))
    print("  readers must glob decisions*.md — /pb:handoff already does")
    return 0


def _siblings(base, name):
    return [os.path.join(base, f) for f in os.listdir(base)
            if re.fullmatch(re.escape(name) + r"-[^.]+\.md", f)]


def main():
    ap = argparse.ArgumentParser(description="Rotate a decisions log by size, losslessly.")
    ap.add_argument("path", help="path to memory/decisions.md")
    ap.add_argument("--threshold-kb", type=float, default=DEFAULT_THRESHOLD_KB)
    ap.add_argument("--apply", action="store_true", help="write (default is a dry run)")
    args = ap.parse_args()
    if not os.path.isfile(args.path):
        print("decisions_rotate: not found: %s" % args.path)
        return 2
    rc = rotate(args.path, args.threshold_kb * 1024, args.apply)
    return 0 if rc == BUSY else rc          # busy is not a failure: the run that holds the lock is doing it


if __name__ == "__main__":
    sys.exit(main())
