#!/usr/bin/env python3
"""
browser_slots.py — pb/tools/browser.py's machine-wide browser limit, with no browser at all.

The failure this pins: four headless Chromiums (about 0.6 GB each) running at once because every pb
command launched its own. Each launch now takes a slot — a counting semaphore across processes made of
`limit` flock'd files — and these are the properties that make it safe to rely on:

  * with a limit of N, the N+1th acquirer WAITS, says so once, and proceeds the moment one lets go
  * a slot is freed when its holder process is killed (the kernel drops the flock — no stale slot)
  * PB_BROWSER_SLOTS (and 0 = off) and PB_BROWSER_WAIT are honoured
  * it fails OPEN: after the wait it prints one `note:` line and proceeds without a slot
  * a symlink / directory / FIFO planted at a slot path (or at the slot directory) is refused — never
    followed, never truncated, never waited on
  * open_browser holds a slot for the browser's life, releases it on close and on a failed launch, and
    appends one line per launch to PB_BROWSER_TRACE

The slot directory lives under the temp dir, so the test points TMPDIR at a folder of its own — it
never touches (or waits on) the slots real runs on this machine are holding.

Usage:  python3 tests/browser_slots.py
Exit:   0 = pass · 1 = a failure
"""
import contextlib
import io
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TMP = tempfile.mkdtemp(prefix="pb-slots-test-")
os.environ["TMPDIR"] = TMP
tempfile.tempdir = TMP
for var in ("PB_BROWSER_SLOTS", "PB_BROWSER_WAIT", "PB_BROWSER_TRACE"):
    os.environ.pop(var, None)
sys.path.insert(0, TOOLS)

import browser  # noqa: E402

FAIL = []
KIDS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


HOLDER = """
import sys, time
sys.path.insert(0, %r)
import browser
s = browser.acquire_slot("a holder process", limit=int(sys.argv[1]), wait=0)
print("held" if s.held else "not-held", s.index, flush=True)
time.sleep(120)
""" % TOOLS


def holder(limit):
    """A separate process holding one slot until it is killed → (Popen, 'held'|'not-held', index)."""
    proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(limit)], stdout=subprocess.PIPE, text=True,
                            env=dict(os.environ, TMPDIR=TMP))
    KIDS.append(proc)
    word, idx = proc.stdout.readline().split()
    return proc, word, idx


def quiet(fn, *a, **k):
    """→ (result, what it wrote to stderr)."""
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        res = fn(*a, **k)
    return res, buf.getvalue()


def fresh_dir():
    shutil.rmtree(browser.slot_dir(), ignore_errors=True)


class FakeBrowser:
    def __init__(self):
        self.closed = False
        self.handlers = {}

    def on(self, event, fn):
        self.handlers[event] = fn

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, fail=False):
        self.fail, self.launched = fail, []

    def launch(self, **kw):
        if self.fail:
            raise RuntimeError("Executable doesn't exist")
        b = FakeBrowser()
        self.launched.append(b)
        return b


class FakePlaywright:
    def __init__(self, fail=False):
        self.chromium = FakeChromium(fail)


def main():
    print("a counting semaphore — the N+1th acquirer waits and proceeds when one releases")
    fresh_dir()
    a = browser.acquire_slot("one", limit=2, wait=5)
    b = browser.acquire_slot("two", limit=2, wait=5)
    check(a.held and b.held and {a.index, b.index} == {0, 1}, "two slots are taken, one each (%s, %s)" % (a.index, b.index))
    got = {}

    def third():
        t0 = time.monotonic()
        res, err = quiet(browser.acquire_slot, "three", 2, 10)
        got.update(slot=res, err=err, waited=time.monotonic() - t0)

    th = threading.Thread(target=third)
    th.start()
    time.sleep(0.8)
    check(th.is_alive() and "slot" not in got, "the third acquirer is still waiting while both slots are held")
    a.release()
    th.join(5)
    check(not th.is_alive() and got.get("slot") is not None and got["slot"].held,
          "…and proceeds once one is released (took slot %s after %.1fs)" % (got["slot"].index if got.get("slot") else "?", got.get("waited", 0)))
    check(got.get("err", "").count("waiting for a browser slot (2 in use)") == 1 and "note:" not in got.get("err", ""),
          "it said so once, not once per poll, and with no fail-open note: %r" % got.get("err"))
    got["slot"].release()
    b.release()
    b.release()
    check(not b.held, "release is idempotent")
    again = browser.acquire_slot("again", limit=2, wait=0)
    check(again.held, "a released slot can be taken again")
    again.release()

    print("browser_slot() — the context manager")
    fresh_dir()
    with browser.browser_slot("cm", limit=1, wait=0) as s1:
        check(s1.held, "the with body holds the slot")
        res, err = quiet(browser.acquire_slot, "other", 1, 0)
        check(not res.held and "note:" in err, "…so a second one (limit 1) does not")
    s2 = browser.acquire_slot("after", limit=1, wait=0)
    check(s2.held, "leaving the with body releases it")
    s2.release()

    print("a slot is freed when its holder process is killed")
    fresh_dir()
    proc, word, idx = holder(1)
    check(word == "held", "a separate process holds the only slot (%s)" % word)
    res, err = quiet(browser.acquire_slot, "me", 1, 0.3)
    check(not res.held and "not honoured" in err, "while it lives, a second acquirer is refused (fails open after its wait)")
    proc.send_signal(signal.SIGKILL)
    proc.wait()
    t0 = time.monotonic()
    res = browser.acquire_slot("me", limit=1, wait=5)
    check(res.held and time.monotonic() - t0 < 2, "kill -9 on the holder frees the slot at once (%.2fs) — no stale slot" % (time.monotonic() - t0))
    res.release()

    print("PB_BROWSER_SLOTS and PB_BROWSER_WAIT are honoured")
    fresh_dir()
    check(browser.slot_limit() == 3, "the default limit is 3")
    os.environ["PB_BROWSER_SLOTS"] = "1"
    check(browser.slot_limit() == 1, "PB_BROWSER_SLOTS=1 → limit 1")
    first = browser.acquire_slot("x", wait=0)
    res, err = quiet(browser.acquire_slot, "y", None, 0)
    check(first.held and not res.held and "limit 1" in err, "…and it is enforced (the second is refused: %r)" % err.strip()[:70])
    first.release()
    os.environ["PB_BROWSER_SLOTS"] = "0"
    held = [browser.acquire_slot("n%d" % i, wait=0) for i in range(6)]
    check(browser.slot_limit() == 0 and all(not h.held for h in held), "PB_BROWSER_SLOTS=0 → no limit: six acquirers, none waits, none holds a file")
    for bad in ("many", "-2", "1.5", ""):
        os.environ["PB_BROWSER_SLOTS"] = bad
        if browser.slot_limit() != 3:
            check(False, "an invalid PB_BROWSER_SLOTS (%r) falls back to the default" % bad)
            break
    else:
        check(True, "an invalid PB_BROWSER_SLOTS (many / -2 / 1.5 / empty) falls back to the default")
    os.environ["PB_BROWSER_SLOTS"] = "1"
    holder_slot = browser.acquire_slot("holder", wait=0)
    os.environ["PB_BROWSER_WAIT"] = "0.6"
    check(browser.slot_wait() == 0.6 and browser.slot_wait(2) == 2.0, "PB_BROWSER_WAIT=0.6 is the wait; an argument beats it")
    t0 = time.monotonic()
    res, err = quiet(browser.acquire_slot, "waiter")
    took = time.monotonic() - t0
    check(not res.held and 0.5 <= took < 3, "…and it is what the acquirer waits (%.2fs for PB_BROWSER_WAIT=0.6)" % took)
    os.environ["PB_BROWSER_WAIT"] = "soon"
    check(browser.slot_wait() == browser.DEFAULT_WAIT == 120.0, "an invalid PB_BROWSER_WAIT falls back to 120")
    holder_slot.release()
    for var in ("PB_BROWSER_SLOTS", "PB_BROWSER_WAIT"):
        os.environ.pop(var, None)

    print("it fails OPEN — after the wait, one note: line and the work goes on")
    fresh_dir()
    h = browser.acquire_slot("hog", limit=1, wait=0)
    t0 = time.monotonic()
    res, err = quiet(browser.acquire_slot, "late", 1, 0.5)
    lines = err.strip().splitlines()
    check(not res.held and time.monotonic() - t0 >= 0.45, "the late acquirer returns after its wait, without a slot")
    check(len(lines) == 2 and lines[0].startswith("waiting for a browser slot (1 in use)") and lines[1].startswith("note: ")
          and "not honoured" in lines[1], "…having printed the waiting line once and one `note:` line: %r" % lines)
    h.release()

    print("a symlink (or anything not a regular file) at a slot path is refused, not followed")
    fresh_dir()
    d = browser.slot_dir()
    os.makedirs(d, mode=0o700)
    victim = os.path.join(TMP, "victim.txt")
    with open(victim, "w") as f:
        f.write("precious")
    os.symlink(victim, os.path.join(d, "slot-0.lock"))
    t0 = time.monotonic()
    res, err = quiet(browser.acquire_slot, "attacker", 1, 30)
    check(not res.held and time.monotonic() - t0 < 2 and "not a regular file" in err,
          "limit 1 with slot-0 a symlink: refused at once (no 30s wait), with a note: %r" % err.strip()[:80])
    check(open(victim).read() == "precious", "…and the file it points at was not written to or truncated")
    res, err = quiet(browser.acquire_slot, "attacker", 2, 5)
    check(res.held and res.index == 1 and open(victim).read() == "precious",
          "limit 2: the symlinked slot is skipped, slot-1 is taken, the victim is untouched")
    res.release()
    os.remove(os.path.join(d, "slot-0.lock"))
    os.mkdir(os.path.join(d, "slot-0.lock"))
    res, err = quiet(browser.acquire_slot, "x", 1, 30)
    check(not res.held and "not a regular file" in err, "a directory at the slot path is refused")
    os.rmdir(os.path.join(d, "slot-0.lock"))
    if hasattr(os, "mkfifo"):
        os.mkfifo(os.path.join(d, "slot-0.lock"))
        t0 = time.monotonic()
        res, err = quiet(browser.acquire_slot, "x", 1, 30)
        check(not res.held and time.monotonic() - t0 < 2 and "not a regular file" in err, "a FIFO at the slot path is refused, and does not block the open")
        os.remove(os.path.join(d, "slot-0.lock"))
    shutil.rmtree(d)
    elsewhere = os.path.join(TMP, "elsewhere")
    os.makedirs(elsewhere)
    os.symlink(elsewhere, d)
    res, err = quiet(browser.acquire_slot, "x", 2, 30)
    check(not res.held and os.listdir(elsewhere) == [] and "not a directory" in err,
          "a symlink where the slot DIRECTORY should be is refused: nothing is created behind it")
    os.remove(d)

    print("the slot directory is private")
    fresh_dir()
    s = browser.acquire_slot("x", limit=1, wait=0)
    mode = stat.S_IMODE(os.stat(browser.slot_dir()).st_mode)
    check(mode == 0o700 and "-%d" % os.getuid() in os.path.basename(browser.slot_dir()),
          "mode 0700, and the uid is in its name (%s %s)" % (oct(mode), os.path.basename(browser.slot_dir())))
    check(stat.S_IMODE(os.stat(os.path.join(browser.slot_dir(), "slot-0.lock")).st_mode) == 0o600, "slot files are 0600")
    s.release()
    os.chmod(browser.slot_dir(), 0o755)
    s = browser.acquire_slot("x", limit=1, wait=0)
    check(s.held and stat.S_IMODE(os.stat(browser.slot_dir()).st_mode) == 0o700, "a directory left open to others is tightened to 0700")
    s.release()

    print("open_browser — a slot for the browser's life, one trace line per launch")
    fresh_dir()
    trace = os.path.join(TMP, "trace.txt")
    os.environ["PB_BROWSER_TRACE"] = trace
    os.environ["PB_BROWSER_SLOTS"] = "1"
    pw = FakePlaywright()
    br = browser.open_browser(pw, "unit")
    res, err = quiet(browser.acquire_slot, "second", None, 0)
    check(isinstance(br, FakeBrowser) and not res.held, "the browser is the Playwright object, and while it is open the slot is taken")
    br.close()
    check(br.closed, "close() still closes the real browser")
    res = browser.acquire_slot("third", wait=0)
    check(res.held, "…and closing it releases the slot")
    res.release()
    br2 = browser.open_browser(pw, "unit")
    br2.handlers["disconnected"](None)
    res = browser.acquire_slot("fourth", wait=0)
    check(res.held, "a browser that disconnects (crashes) releases its slot too")
    res.release()
    try:
        browser.open_browser(FakePlaywright(fail=True), "unit")
        check(False, "a failed launch raises")
    except RuntimeError:
        res = browser.acquire_slot("fifth", wait=0)
        check(res.held, "a failed launch propagates its error AND gives the slot back")
        res.release()
    with open(trace, encoding="utf-8") as f:
        rows = [ln.split() for ln in f.read().splitlines()]
    check(len(rows) == 2 and all(len(r) == 3 and r[1] == str(os.getpid()) and r[2] == "unit" for r in rows)
          and rows[0][0].endswith("Z"), "PB_BROWSER_TRACE: one `<iso time> <pid> <who>` line per successful launch (%d)" % len(rows))
    for var in ("PB_BROWSER_TRACE", "PB_BROWSER_SLOTS"):
        os.environ.pop(var, None)

    print("is_loopback_url — the tools open pb previews, not the web")
    for url, want in (("http://127.0.0.1:8000/", True), ("http://localhost:5173/x?y=1", True), ("http://[::1]:9/", True),
                      ("https://127.0.0.1/", False), ("http://example.com/", False), ("http://127.0.0.1.evil.test/", False),
                      ("http://localhost@evil.test/", False), ("file:///etc/passwd", False), ("javascript:alert(1)", False), ("", False)):
        check(browser.is_loopback_url(url) is want, "%-34s → %s" % (url or "(empty)", want))


try:
    main()
finally:
    for proc in KIDS:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        proc.stdout.close()
    shutil.rmtree(TMP, ignore_errors=True)

if FAIL:
    print("\n✗ %d failure(s)" % len(FAIL))
    sys.exit(1)
print("\n✓ browser limit: a real semaphore, freed by the kernel, fail-open, and it will not follow a symlink")
