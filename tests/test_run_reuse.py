#!/usr/bin/env python3
"""
test_run_reuse.py — test_run.py reuses the project's running preview, runs the whole battery in one
browser, and leaves nothing behind.

The failure this pins: 156 of 183 test runs on one project booted a private serve.py AND a private
browser each — and `--functional`, `--roles` and `--server` ran as three separate processes, so one
`/pb:test` started three of each. Now:

  stdlib half (runs everywhere)
  * a project with a running preview: the runner's transport is an attach to THAT server (and prints
    `reusing the running preview at <url>`); no second serve.py starts
  * none running: it boots its own, and when it is done no serve.py of that project is left
  * `--isolated` boots a private one even when the preview is up — and puts the project's own
    .preview/server.json back afterwards (serve.py drops the record when it stops, which would have
    made the preview that is still running invisible to `explore.py link`)
  * `--attach URL` is taken as given (unchanged)
  * a record that points at ANOTHER registry's server, at a dead port, or at a host that is not this
    machine is never reused
  * `--all` with no Playwright → exit 3 ("could not run"), and boots no server for it
  * `--all` combined with a mode flag, or `--isolated` with `--attach`, is a usage error (2)

  browser half (Playwright; skipped cleanly without it)
  * a run with the preview up boots no second serve.py and prints the reuse line
  * a run with none up boots exactly one and leaves no process of its own alive (process group empty)
  * `--isolated` boots a second one while the preview stays up
  * `--all` records exactly ONE browser launch in the PB_BROWSER_TRACE file (three single-mode runs
    record three), prints each mode under its own header, exits with the worst of the three codes,
    and `--json` carries each mode's own payload under {"mode": "all", "modes": {…}}

Usage:  python3 tests/test_run_reuse.py
Exit:   0 = pass · 1 = a failure
"""
import contextlib
import importlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TEST_RUN = os.path.join(TOOLS, "test_run.py")
GOLDEN = os.path.join(ROOT, "fixtures", "golden")
sys.path.insert(0, TOOLS)
for var in ("PB_BROWSER_TRACE", "PB_BROWSER_SLOTS", "PB_BROWSER_WAIT"):
    os.environ.pop(var, None)

import browser  # noqa: E402
import explore  # noqa: E402
tr = importlib.import_module("test_run")

FAIL = []
TMPS = []
STARTED = []        # pids of previews this test started — killed in `finally`


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


def project():
    """A temp copy of the golden fixture → (registry path, folder)."""
    d = tempfile.mkdtemp(prefix="pb-reuse-")
    TMPS.append(d)
    shutil.copytree(os.path.join(GOLDEN, "render"), os.path.join(d, "render"))
    shutil.copy(os.path.join(GOLDEN, "registry.json"), os.path.join(d, "registry.json"))
    return os.path.join(d, "registry.json"), d


def procs(marker, name="serve.py"):
    """Live processes whose command line has `name` and `marker` (the project's folder name)."""
    out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True).stdout
    rows = []
    for ln in out.splitlines():
        if name in ln and marker in ln:
            rows.append(int(ln.split(None, 1)[0]))
    return rows


def group_alive(pgid):
    """Processes still alive in a process group (zombies do not count)."""
    out = subprocess.run(["ps", "-axo", "pgid=,stat=,pid="], capture_output=True, text=True).stdout
    return [ln for ln in out.splitlines() if ln.split() and ln.split()[0] == str(pgid) and not ln.split()[1].startswith("Z")]


def wait_gone(fn, secs=6.0):
    end = time.time() + secs
    while time.time() < end:
        if not fn():
            return True
        time.sleep(0.2)
    return not fn()


def start_preview(reg):
    rec = explore._start_server(reg)
    STARTED.append(rec["pid"])
    return rec


def stop_preview(rec):
    try:
        os.kill(rec["pid"], signal.SIGTERM)
    except OSError:
        pass
    wait_gone(lambda: explore._get(rec["url"].rstrip("/") + "/__pb_health")[0] == 200)


def capture(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = fn(*a, **k)
    return res, buf.getvalue()


def stdlib_half():
    print("no preview running → a private one, stopped at the end")
    reg, d = project()
    mark = os.path.basename(d)
    t = tr._transport(reg, None)
    check(isinstance(t, tr.Server), "the transport is a private Server")
    with t as srv:
        check(srv.url.startswith("http://127.0.0.1:") and len(procs(mark)) == 1, "…one serve.py for this project is up (%s)" % srv.url)
    check(wait_gone(lambda: procs(mark)), "…and none is left when the run is over")
    check(not os.path.exists(os.path.join(d, explore.SERVER_FILE)), "…with no record left behind")

    print("this project's preview running → reuse it")
    rec = start_preview(reg)
    try:
        check(len(procs(mark)) == 1, "the project's preview is up (pid %s)" % rec["pid"])
        check(browser.find_preview(reg) == rec["url"].rstrip("/") + "/", "find_preview returns its URL (with a trailing /)")
        t, out = capture(tr._transport, reg, None)
        check(isinstance(t, tr._Attached) and t.url == rec["url"].rstrip("/") + "/", "the transport is an attach to that server")
        check(out.strip() == "reusing the running preview at %s" % t.url, "…and says so: %r" % out.strip())
        with t as srv:
            check(len(procs(mark)) == 1, "entering it starts no second serve.py")
        check(len(procs(mark)) == 1, "…and leaving it stops nothing")
        t, out = capture(tr._transport, reg, "http://127.0.0.1:1/")
        check(isinstance(t, tr._Attached) and t.url == "http://127.0.0.1:1/" and out == "", "--attach URL is taken as given, and prints nothing")

        t, out = capture(tr._transport, reg, None, True)
        check(isinstance(t, tr.Server) and "reusing" not in out, "--isolated: a private Server even though the preview is up")
        before = open(os.path.join(d, explore.SERVER_FILE), encoding="utf-8").read()
        with t as srv:
            check(len(procs(mark)) == 2 and srv.url.rstrip("/") != rec["url"].rstrip("/"), "…it really is a second serve.py")
        check(wait_gone(lambda: len(procs(mark)) != 1), "…which is gone afterwards; the project's preview still runs")
        after = explore.server_record(d)
        check(after is not None and after.get("pid") == rec["pid"] and explore._ours(after["url"].rstrip("/"), reg),
              "…and the project's preview record was put back (it names pid %s)" % (after or {}).get("pid"))
        check(open(os.path.join(d, explore.SERVER_FILE), encoding="utf-8").read() == before, "…byte for byte")

        print("a record that is not this project's preview is never reused")
        reg2, d2 = project()
        os.makedirs(os.path.join(d2, ".preview"))
        with open(os.path.join(d2, explore.SERVER_FILE), "w", encoding="utf-8") as f:
            json.dump({"url": rec["url"], "pid": rec["pid"], "registry": reg2}, f)
        check(explore._get(rec["url"].rstrip("/") + "/__pb_health")[0] == 200, "(the server the record names is up)")
        check(browser.find_preview(reg2) is None, "a record pointing at ANOTHER registry's server → no preview found")
        t, out = capture(tr._transport, reg2, None)
        check(isinstance(t, tr.Server) and "reusing" not in out, "…so the runner boots its own instead of attaching to it")
        with open(os.path.join(d2, explore.SERVER_FILE), "w", encoding="utf-8") as f:
            json.dump({"url": "http://127.0.0.1:1/", "pid": 1, "registry": reg2}, f)
        check(browser.find_preview(reg2) is None, "a record naming a dead port → none")
        t0 = time.time()
        with open(os.path.join(d2, explore.SERVER_FILE), "w", encoding="utf-8") as f:
            json.dump({"url": "http://192.0.2.1:9/", "pid": 1, "registry": reg2}, f)
        check(browser.find_preview(reg2) is None and time.time() - t0 < 1.5, "a record naming a host that is not this machine → none, without a request")
        os.remove(os.path.join(d2, explore.SERVER_FILE))
        check(browser.find_preview(reg2) is None, "no record at all → none (it never probes ports)")
    finally:
        stop_preview(rec)
    check(wait_gone(lambda: procs(mark)), "the preview this test started is stopped")

    print("usage + could-not-run")
    reg, d = project()
    mark = os.path.basename(d)
    for argv, want in ((["--all", "--roles"], "do not combine"), (["--isolated", "--attach", "http://127.0.0.1:1/"], "opposites")):
        r = subprocess.run([sys.executable, TEST_RUN, reg] + argv, capture_output=True, text=True)
        check(r.returncode == 2 and want in r.stderr, "%s → exit 2 (%s)" % (" ".join(argv), want))
    runner = ("import sys, runpy; sys.modules['playwright'] = None; sys.argv = ['test_run.py', %r, '--all']; "
              "runpy.run_path(%r, run_name='__main__')" % (reg, TEST_RUN))
    r = subprocess.run([sys.executable, "-c", runner], capture_output=True, text=True, timeout=60)
    check(r.returncode == 3 and "cannot run: Playwright not installed" in r.stdout and "--all: functional exit 3" in r.stdout,
          "--all without Playwright → exit 3, cannot run (rc=%s)" % r.returncode)
    check(procs(mark) == [], "…and it booted no server for it")


def run_runner(args, env=None, mark=None, sample=True):
    """Run test_run.py in its own session → (rc, stdout, the most serve.py processes seen at once, pgid)."""
    proc = subprocess.Popen([sys.executable, TEST_RUN] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            env=dict(os.environ, **(env or {})), start_new_session=True)
    most = 0
    out = ""
    deadline = time.time() + 240
    while proc.poll() is None and time.time() < deadline:
        if sample and mark:
            most = max(most, len(procs(mark)))
        time.sleep(0.15)
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGKILL)
    out = proc.stdout.read()
    proc.stdout.close()
    return proc.wait(), out, most, proc.pid


def browser_half():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print("  – skipped: Playwright is not installed (pip install playwright && playwright install chromium)")
        return

    print("with the project's preview up: no second serve.py, the reuse line is printed")
    reg, d = project()
    mark = os.path.basename(d)
    rec = start_preview(reg)
    try:
        url = rec["url"].rstrip("/") + "/"
        rc, out, most, _ = run_runner([reg, "--functional"], mark=mark)
        check(rc == 0, "--functional passes against the golden (rc=%s)" % rc)
        check(("reusing the running preview at " + url) in out, "it prints `reusing the running preview at %s`" % url)
        check(most == 1, "…and at no moment was a second serve.py running (most at once: %d)" % most)
        check((explore.server_record(d) or {}).get("pid") == rec["pid"], "…the preview's record is untouched")

        rc, out, most, _ = run_runner([reg, "--functional", "--isolated"], mark=mark)
        check(rc == 0 and "reusing" not in out and most == 2, "--isolated boots its own beside it (most at once: %d)" % most)
        check(len(procs(mark)) == 1 and (explore.server_record(d) or {}).get("pid") == rec["pid"],
              "…and afterwards only the project's preview is left, still recorded")
    finally:
        stop_preview(rec)
    check(wait_gone(lambda: procs(mark)), "the preview this test started is stopped")

    print("with none running: exactly one private server, and nothing of the run is left alive")
    reg, d = project()
    mark = os.path.basename(d)
    rc, out, most, pgid = run_runner([reg, "--functional"], mark=mark)
    check(rc == 0 and "reusing" not in out and most == 1, "it boots one serve.py of its own (rc=%s, most at once: %d)" % (rc, most))
    check(wait_gone(lambda: group_alive(pgid)) and procs(mark) == [],
          "…and afterwards no process of the run is alive (%s)" % (group_alive(pgid) or "none"))

    print("--all: one browser launch for the whole battery")
    reg, d = project()
    mark = os.path.basename(d)
    trace = os.path.join(d, "trace.txt")
    singles = {}
    for mode in ("functional", "roles", "server"):
        out_json = os.path.join(d, "single-%s.json" % mode)
        rc, out, _m, _p = run_runner([reg, "--" + mode, "--json", out_json], env={"PB_BROWSER_TRACE": trace}, sample=False)
        with open(out_json, encoding="utf-8") as f:
            singles[mode] = (rc, json.load(f))
    with open(trace, encoding="utf-8") as f:
        n_single = len(f.read().splitlines())
    check(n_single == 3, "three single-mode runs launch three browsers (%d trace lines)" % n_single)
    os.remove(trace)
    all_json = os.path.join(d, "all.json")
    rc, out, most, pgid = run_runner([reg, "--all", "--json", all_json], env={"PB_BROWSER_TRACE": trace}, mark=mark)
    with open(trace, encoding="utf-8") as f:
        rows = f.read().splitlines()
    check(len(rows) == 1, "--all records exactly ONE browser launch in PB_BROWSER_TRACE (%d)" % len(rows))
    check(most == 1, "…over one transport: one serve.py (most at once: %d)" % most)
    for mode in ("functional", "roles", "server"):
        check(("── test_run.py --all · %s ──" % mode) in out and ("test_run.py --%s:" % mode) in out,
              "%s prints its findings under its own header" % mode)
    want = max(c for c, _j in singles.values())
    check(rc == want, "it exits with the worst code of its modes (%s → %d; got %d)" % (
        ", ".join("%s %d" % (m, c) for m, (c, _j) in singles.items()), want, rc))
    check("--all: " + " · ".join("%s exit %d" % (m, c) for m, (c, _j) in singles.items()) in out, "…and the last line names each mode's code")
    with open(all_json, encoding="utf-8") as f:
        merged = json.load(f)
    check(merged.get("mode") == "all" and list(merged.get("modes", {})) == ["functional", "roles", "server"],
          "--json: {\"mode\": \"all\", \"modes\": {functional, roles, server}}")
    check(all(merged["modes"][m] == singles[m][1] for m in singles),
          "…each value is exactly what that mode writes on its own")
    check(wait_gone(lambda: group_alive(pgid)) and procs(mark) == [], "nothing of the --all run is left alive")


def main():
    print("— stdlib half —")
    stdlib_half()
    print("— browser half —")
    browser_half()


try:
    main()
finally:
    for pid in STARTED:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    time.sleep(0.3)
    for d in TMPS:
        shutil.rmtree(d, ignore_errors=True)

if FAIL:
    print("\n✗ %d failure(s)" % len(FAIL))
    sys.exit(1)
print("\n✓ test_run.py: reuses the project's preview, one browser for --all, and leaves nothing running")
