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

print()
if fails:
    print("FAIL — %d check(s)" % len(fails))
    sys.exit(1)
print("PASS — rotation moves whole entries by date, and never loses one")
