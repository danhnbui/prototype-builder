#!/usr/bin/env python3
"""
decisions_rotate.py — keep `memory/decisions.md` small enough to read (D-21·4).

The why-log only grows. A real project reached **187 entries / 875 KB in two months**, which is
the file three commands append to and — since v1.12.0 — grep before appending. Past a point the
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

Readers must glob `decisions*.md`. `/pb:handoff-close` already does (its bundle would otherwise
ship a history that stops at the first rotation, silently).

  decisions_rotate.py <memory/decisions.md>            # dry run: what would move, and where
  decisions_rotate.py <memory/decisions.md> --apply
  decisions_rotate.py <memory/decisions.md> --threshold-kb 250 --apply

Exit: 0 = clean (or nothing to do) · 2 = aborted, nothing changed.
"""
import argparse
import datetime
import os
import re
import shutil
import sys

DEFAULT_THRESHOLD_KB = 500
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


def rotate(path, threshold, apply_=False):
    with open(path, encoding="utf-8") as f:
        original = f.read()
    preamble, live_entries = split_entries(original)
    base0 = os.path.dirname(os.path.abspath(path))
    name0 = os.path.splitext(os.path.basename(path))[0]
    # The invariant is about the whole `decisions*.md` FAMILY, not this one file. A second
    # rotation appends to a sibling that already holds history; comparing the live file's
    # entries against the family afterwards reports every previously-archived entry as an
    # extra, and the abort path then "rolls back" history it never wrote.
    family_before = list(live_entries)
    for sib in sorted(_siblings(base0, name0)):
        with open(sib, encoding="utf-8") as f:
            family_before += split_entries(f.read())[1]
    all_entries = live_entries
    size_kb = len(original.encode("utf-8")) / 1024
    keep, move = plan(original, threshold)

    if not move:
        print("decisions_rotate: %s is %.0f KB / %d entries — under the %.0f KB threshold, nothing to do"
              % (os.path.basename(path), size_kb, len(all_entries), threshold / 1024))
        return 0

    by_year = {}
    for e in move:
        by_year.setdefault(entry_year(e) or "undated", []).append(e)
    base = os.path.dirname(os.path.abspath(path))
    name = os.path.splitext(os.path.basename(path))[0]
    kept_bytes = len((preamble + "".join(keep)).encode("utf-8"))

    print("decisions_rotate: %s — %.0f KB / %d entries, threshold %.0f KB"
          % (os.path.basename(path), size_kb, len(all_entries), threshold / 1024))
    print("  keep  %3d entries  (%.0f KB)" % (len(keep), kept_bytes / 1024))
    for year in sorted(by_year):
        chunk = by_year[year]
        print("  move  %3d entries  (%.0f KB)  -> %s-%s.md"
              % (len(chunk), sum(len(e.encode("utf-8")) for e in chunk) / 1024, name, year))
    if not apply_:
        print("\n(Dry run — nothing written. Pass --apply.)")
        return 0

    bdir = os.path.join(base, ".pb-backups")
    os.makedirs(bdir, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = os.path.join(bdir, "%s.%s.md" % (name, stamp))
    shutil.copy2(path, backup)
    # Back up EVERY file this run will touch, not just the live one. A sibling that already
    # holds archived entries is history too, and the rollback must put it back as it was —
    # an earlier version deleted it instead, losing 98 entries it had never written.
    prior = {}
    for year in by_year:
        sib = os.path.join(base, "%s-%s.md" % (name, year))
        if os.path.isfile(sib):
            sib_backup = os.path.join(bdir, "%s-%s.%s.md" % (name, year, stamp))
            shutil.copy2(sib, sib_backup)
            prior[sib] = sib_backup

    def _restore():
        shutil.copy2(backup, path)
        for target, saved in prior.items():
            shutil.copy2(saved, target)
        for f_ in written:
            if f_ not in prior:
                try:
                    os.remove(f_)          # only files this run CREATED
                except OSError:
                    pass

    written = []
    try:
        for year, chunk in sorted(by_year.items()):
            sib = os.path.join(base, "%s-%s.md" % (name, year))
            existing = ""
            if os.path.isfile(sib):
                with open(sib, encoding="utf-8") as f:
                    existing = f.read()
                _, prior = split_entries(existing)
                chunk = prior + [e for e in chunk if e not in prior]
            with open(sib, "w", encoding="utf-8") as f:
                f.write(sibling_note(year, os.path.basename(path)) + "".join(chunk))
            written.append(sib)
        with open(path, "w", encoding="utf-8") as f:
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
    print("  readers must glob decisions*.md — /pb:handoff-close already does")
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
    return rotate(args.path, args.threshold_kb * 1024, args.apply)


if __name__ == "__main__":
    sys.exit(main())
