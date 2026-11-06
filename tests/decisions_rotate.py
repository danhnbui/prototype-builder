#!/usr/bin/env python3
"""
decisions_rotate.py — the why-log rotation (D-21·4).

Five files told users their glob must be `decisions*.md` "because rotation moves older entries",
and for one release nothing rotated. This is that mechanism, and these are the properties that
make it safe to point at someone's history:

  1. under the threshold it does nothing, and says so
  2. it moves whole entries chosen BY THEIR OWN DATE — a real log runs 22 August entries, then
     86 July, then 78 August, so "the tail" is not "the oldest"
  3. an entry whose heading carries no date is never moved
  4. a second rotation appends to the existing sibling and keeps what was already archived
  5. on a verification mismatch it RESTORES every file it touched — including a sibling that
     already held history. An earlier version deleted that sibling, losing 98 entries it had
     never written. This is the case that found it.

Usage: python3 tests/decisions_rotate.py · Exit 0/1.
"""
import importlib.util
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "decisions_rotate", os.path.join(ROOT, "pb", "tools", "decisions_rotate.py"))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


PRE = "# Decisions — t\n\n> the house note\n\n"


def entry(date, title, pad=0):
    return "## %s — %s\n- **Decision:** x\n%s\n" % (date, title, "y\n" * pad)


def write(d, name, text):
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        f.write(text)
    return os.path.join(d, name)


def entries_in(path):
    with open(path, encoding="utf-8") as f:
        return R.split_entries(f.read())[1]


def family(d):
    out = []
    for f in sorted(os.listdir(d)):
        if re.fullmatch(r"decisions.*\.md", f):
            out += entries_in(os.path.join(d, f))
    return out


print("1 · under the threshold, nothing happens")
d = tempfile.mkdtemp()
p = write(d, "decisions.md", PRE + entry("2026-08-02", "a") + entry("2026-07-01", "b"))
before = open(p, encoding="utf-8").read()
check(R.rotate(p, 500 * 1024, apply_=True) == 0, "exits 0")
check(open(p, encoding="utf-8").read() == before, "and does not touch the file")
check(not os.path.exists(os.path.join(d, "decisions-2026.md")), "no sibling is created")

print("2 · it chooses by DATE, not by position")
d = tempfile.mkdtemp()
# File order puts the OLDEST entry first and a new one last — rotating "the tail" would be wrong.
p = write(d, "decisions.md", PRE + entry("2026-07-01", "oldest", 400)
          + entry("2026-09-01", "newest", 400) + entry("2026-08-01", "middle", 400))
R.rotate(p, 2 * 1024, apply_=True)
kept = [e.split("\n")[0] for e in entries_in(p)]
moved = [e.split("\n")[0] for e in entries_in(os.path.join(d, "decisions-2026.md"))]
check(any("newest" in k for k in kept), "the newest entry stays even though it is not first in the file")
check(any("oldest" in m for m in moved), "the oldest moves even though it IS first in the file")
check(len(kept) + len(moved) == 3, "all three entries still exist")

print("3 · an undated entry is pinned")
d = tempfile.mkdtemp()
p = write(d, "decisions.md", PRE + entry("2026-07-01", "dated-old", 400)
          + entry("2026-09-01", "dated-new", 400)
          + "## no date here — a heading with no date\n- **Decision:** x\n" + "y\n" * 400 + "\n")
code = R.rotate(p, 2 * 1024, apply_=True)
moved = entries_in(os.path.join(d, "decisions-2026.md")) if os.path.exists(
    os.path.join(d, "decisions-2026.md")) else []
check(code == 0 and moved, "the file really did rotate (%d entries moved)" % len(moved))
check(any("no date here" in e for e in entries_in(p)),
      "the undated entry stays in the live file — not being able to date it is a reason "
      "to leave it alone")
check(not any("no date here" in e for e in moved), "and it is not in the sibling")

print("4 · a second rotation appends to the sibling")
d = tempfile.mkdtemp()
p = write(d, "decisions.md", PRE + "".join(entry("2026-0%d-01" % m, "e%d" % m, 300) for m in range(1, 8)))
n0 = len(entries_in(p))
R.rotate(p, 3 * 1024, apply_=True)
after_one = len(family(d))
R.rotate(p, 1 * 1024, apply_=True)
check(len(family(d)) == n0 == after_one,
      "every entry survives two rotations (%d before, %d after)" % (n0, len(family(d))))
check(sorted(family(d)) == sorted(R.split_entries(PRE + "".join(
      entry("2026-0%d-01" % m, "e%d" % m, 300) for m in range(1, 8)))[1]),
      "and each is byte-identical to what was written")

print("5 · a verification mismatch RESTORES, it never deletes")
d = tempfile.mkdtemp()
p = write(d, "decisions.md", PRE + "".join(entry("2026-0%d-01" % m, "e%d" % m, 300) for m in range(1, 6)))
sib = write(d, "decisions-2025.md", "# archived\n\n" + entry("2025-01-01", "history-that-predates-this-run"))
sib_before = open(sib, encoding="utf-8").read()
live_before = open(p, encoding="utf-8").read()
_real = R.split_entries
R.split_entries = lambda t: (_real(t)[0], _real(t)[1][:-1] if _real(t)[1] else [])  # lose one on read-back
try:
    code = R.rotate(p, 1 * 1024, apply_=True)
finally:
    R.split_entries = _real
check(code == 2, "it aborts with exit 2")
check(os.path.isfile(sib) and open(sib, encoding="utf-8").read() == sib_before,
      "the pre-existing sibling is still there, byte-identical — the bug this test was written for")
check(open(p, encoding="utf-8").read() == live_before, "and the live file is back as it was")

import contextlib
import io
import stat
import subprocess
import time

TOOL = os.path.join(ROOT, "pb", "tools", "decisions_rotate.py")


def read(p):
    with open(p, "rb") as f:
        return f.read()


def quiet(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rv = fn(*a)
    return rv, buf.getvalue()


def lock_of(d):
    return os.path.join(d, R.LOCK_NAME)


def fixture_with_2025_sibling():
    d = tempfile.mkdtemp()
    p = write(d, "decisions.md", PRE + entry("2025-03-01", "old-a", 600) + entry("2025-04-01", "old-b", 600)
              + entry("2026-09-01", "new", 600))
    sib = write(d, "decisions-2025.md", "# archived\n\n" + entry("2025-01-01", "history-already-archived"))
    return d, p, sib


print("6 · an existing sibling that cannot be written: no traceback, both files byte-identical")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    print("  skip (root ignores 0444)")
else:
    d, p, sib = fixture_with_2025_sibling()
    os.chmod(sib, 0o444)
    live_before, sib_before = read(p), read(sib)
    try:
        err = None
        code, out = quiet(R.rotate, p, 2 * 1024, True)
    except Exception as e:  # noqa: BLE001
        err, code, out = e, None, ""
    check(err is None, "no exception (%r)" % (err,))
    check(code == 2, "aborts with exit 2 (%r)" % (code,))
    check(read(p) == live_before, "the live file is byte-identical")
    check(read(sib) == sib_before and stat.S_IMODE(os.stat(sib).st_mode) == 0o444,
          "the read-only sibling is byte-identical and still 0444")
    check(not os.path.exists(lock_of(d)), "the lock is released after a failure")
    r = subprocess.run([sys.executable, TOOL, p, "--threshold-kb", "2", "--apply"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    check("Traceback" not in r.stderr and r.returncode == 2 and read(p) == live_before and read(sib) == sib_before,
          "the CLI: no traceback, exit 2, files untouched")
    os.chmod(sib, 0o644)

print("6b · a lossless-check failure with an existing sibling restores the sibling too")
d, p, sib = fixture_with_2025_sibling()
live_before, sib_before = read(p), read(sib)
_real, _note, flag = R.split_entries, R.sibling_note, {"writing": False}


def _noting(year, source):
    flag["writing"] = True                   # from here on, reads lose an entry
    return _note(year, source)


def _lossy(t):
    pre, ents = _real(t)
    return pre, (ents[:-1] if flag["writing"] and ents else ents)


R.sibling_note, R.split_entries = _noting, _lossy
try:
    try:
        err = None
        code, out = quiet(R.rotate, p, 2 * 1024, True)
    except Exception as e:  # noqa: BLE001
        err, code = e, None
finally:
    R.sibling_note, R.split_entries = _note, _real
check(err is None and code == 2, "aborts with exit 2, no exception (%r, %r)" % (code, err))
check(read(sib) == sib_before, "the sibling that already held history is back as it was")
check(read(p) == live_before, "and so is the live file")
check(sorted(os.listdir(d)) == [".pb-backups", "decisions-2025.md", "decisions.md"],
      "and nothing else was left behind (%s)" % sorted(os.listdir(d)))

print("7 · the lock")
d, p, sib = fixture_with_2025_sibling()
live_before, sib_before = read(p), read(sib)
with open(lock_of(d), "w") as f:
    f.write("999999 held\n")
code, out = quiet(R.rotate, p, 2 * 1024, True)
check(code == R.BUSY, "a held lock -> rotate returns %r (%r)" % (R.BUSY, code))
check(read(p) == live_before and read(sib) == sib_before and not os.path.exists(os.path.join(d, ".pb-backups")),
      "and nothing changed: no write, no backup")
check(os.path.exists(lock_of(d)), "the lock it did not take is left alone")
check(len(out.strip().splitlines()) == 1 and "busy" in out, "it says so in one line: %r" % out.strip())
r = subprocess.run([sys.executable, TOOL, p, "--threshold-kb", "2", "--apply"],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
check(r.returncode == 0 and len(r.stdout.strip().splitlines()) == 1 and read(p) == live_before,
      "the CLI exits 0 with one line and changes nothing (rc=%d)" % r.returncode)
r = subprocess.run([sys.executable, TOOL, p, "--threshold-kb", "2"],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
check(r.returncode == 0 and "Dry run" in r.stdout, "a dry run does not need the lock")
old = time.time() - (R.LOCK_STALE_S + 60)
os.utime(lock_of(d), (old, old))
check(not R.lock_is_fresh(p), "a lock older than 10 minutes is not fresh")
code, out = quiet(R.rotate, p, 2 * 1024, True)
check(code == 0 and read(p) != live_before and not os.path.exists(lock_of(d)),
      "a stale lock is removed and retaken; the run rotates and releases it")
check(len(family(d)) == 4, "and every entry is still there (%d)" % len(family(d)))
d = tempfile.mkdtemp()
p = write(d, "decisions.md", PRE + entry("2026-08-02", "a") + entry("2026-07-01", "b"))
code, out = quiet(R.rotate, p, 500 * 1024, True)
check(code == 0 and not os.path.exists(lock_of(d)), "nothing to do: exit 0 and no lock left behind")

print("8 · an append that lands mid-rotation is detected, and never lost")
for label, hook_name in (("after the backup copy", "copy2"), ("after the siblings are written", "sibling_note")):
    d, p, sib = fixture_with_2025_sibling()
    sib_before = read(sib)
    appended = entry("2026-10-01", "appended-meanwhile", 5)
    fired = {"n": 0}

    def _append():
        if not fired["n"]:
            fired["n"] = 1
            with open(p, "a", encoding="utf-8") as f:
                f.write(appended)

    _copy2, _note = R.shutil.copy2, R.sibling_note
    if hook_name == "copy2":
        def _c2(src, dst, *a, **k):
            rv = _copy2(src, dst, *a, **k)
            if os.path.abspath(src) == os.path.abspath(p):
                _append()
            return rv
        R.shutil.copy2 = _c2
    else:
        def _sn(year, source):
            _append()
            return _note(year, source)
        R.sibling_note = _sn
    try:
        try:
            err = None
            code, out = quiet(R.rotate, p, 2 * 1024, True)
        except Exception as e:  # noqa: BLE001
            err, code = e, None
    finally:
        R.shutil.copy2, R.sibling_note = _copy2, _note
    check(err is None and code == 2, "%s: aborts with exit 2 (%r, %r)" % (label, code, err))
    live_after = open(p, encoding="utf-8").read()
    check(appended in live_after, "  the appended entry is still in the live file")
    check(all(e in live_after for e in R.split_entries(PRE + entry("2025-03-01", "old-a", 600)
                                                       + entry("2025-04-01", "old-b", 600)
                                                       + entry("2026-09-01", "new", 600))[1]),
          "  and so is every entry that was there before")
    check(read(sib) == sib_before, "  the sibling is byte-identical")
    check(not os.path.exists(lock_of(d)), "  the lock is released")
    code, out = quiet(R.rotate, p, 2 * 1024, True)
    check(code == 0 and len(family(d)) == 5, "  a second run, nothing racing, rotates: 5 entries across the family (%d)"
          % len(family(d)))

print()
if fails:
    print("FAIL — %d check(s)" % len(fails))
    sys.exit(1)
print("PASS — rotation moves whole entries by date, and never loses one")
