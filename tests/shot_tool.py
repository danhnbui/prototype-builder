#!/usr/bin/env python3
"""
shot_tool.py — shot.py, the one way pb looks at a screen.

The failure this pins: every look at a render was a hand-written Playwright script that started its own
serve.py and its own browser (740 of 929 browser runs on one project), and left them running when the
script forgot to clean up. shot.py is that, once — and it is a tool for pb previews, not a browser:

  stdlib half (runs everywhere)
  * exactly one of --screen / --path / --url; a bad viewport, a --path that is not a path on the
    preview, an --out that is a symlink → exit 2
  * `--url` takes only http://127.0.0.1 / http://localhost — any other host or scheme → exit 2, before
    anything starts
  * no Playwright → exit 3 ("cannot run"), and no server was booted for it
  * the output-path rules (default folder, a .png file, several viewports)

  browser half (Playwright; skipped cleanly without it)
  * PNGs at two viewports for a screen of the golden fixture, written where the output says, one line
    per file, at exactly the viewport's size — through ONE browser launch
  * it reuses the project's running preview (no second serve.py); with none running it boots one for the
    run and leaves nothing alive
  * --role, --selector, --click, --wait-for, --eval, --console, --full-page, --out FILE
  * a screen or selector that is not there → exit 1, and no PNG pretends it was

Usage:  python3 tests/shot_tool.py
Exit:   0 = pass · 1 = a failure
"""
import json
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
SHOT = os.path.join(TOOLS, "shot.py")
GOLDEN = os.path.join(ROOT, "fixtures", "golden")
sys.path.insert(0, TOOLS)
for var in ("PB_BROWSER_TRACE", "PB_BROWSER_SLOTS", "PB_BROWSER_WAIT"):
    os.environ.pop(var, None)

import explore  # noqa: E402
import shot     # noqa: E402

FAIL = []
TMPS = []
STARTED = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


def project():
    d = tempfile.mkdtemp(prefix="pb-shot-")
    TMPS.append(d)
    shutil.copytree(os.path.join(GOLDEN, "render"), os.path.join(d, "render"))
    shutil.copy(os.path.join(GOLDEN, "registry.json"), os.path.join(d, "registry.json"))
    return os.path.join(d, "registry.json"), d


def run(args, cwd=None, env=None, timeout=120):
    r = subprocess.run([sys.executable, SHOT] + args, capture_output=True, text=True, cwd=cwd, timeout=timeout,
                       env=dict(os.environ, **(env or {})))
    return r.returncode, r.stdout, r.stderr


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def procs(marker):
    out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True).stdout
    return [ln for ln in out.splitlines() if "serve.py" in ln and marker in ln]


def wait_gone(fn, secs=6.0):
    end = time.time() + secs
    while time.time() < end:
        if not fn():
            return True
        time.sleep(0.2)
    return not fn()


def stdlib_half():
    reg, d = project()
    mark = os.path.basename(d)
    print("usage — refused before anything starts")
    for argv, why in (([], "no target"),
                      (["--screen", "login", "--path", "/design-system"], "two targets"),
                      (["--screen", "login", "--url", "http://127.0.0.1:9/"], "two targets (screen + url)"),
                      (["--url", "http://example.com/"], "--url on another host"),
                      (["--url", "https://127.0.0.1:9/"], "--url over https"),
                      (["--url", "http://127.0.0.1.evil.test/"], "--url on a look-alike host"),
                      (["--url", "http://localhost@evil.test/"], "--url with credentials"),
                      (["--url", "file:///etc/hosts"], "--url a file"),
                      (["--path", "//evil.test/x"], "--path that names another host"),
                      (["--path", "design-system"], "--path without a leading /"),
                      (["--screen", "login", "--viewport", "wide"], "a viewport that is not WxH"),
                      (["--screen", "login", "--viewport", "20x20"], "a viewport under 100px"),
                      (["--screen", "login", "--wait", "-5"], "a negative --wait")):
        rc, out, err = run([reg] + argv)
        check(rc == 2 and "S-USAGE" in err and out == "", "%s → exit 2" % why)
    rc, out, err = run([os.path.join(d, "nope.json"), "--screen", "login"])
    check(rc == 2 and "file not found" in err, "a registry that does not exist → exit 2")
    link = os.path.join(d, "out-link")
    os.symlink(d, link)
    rc, out, err = run([reg, "--screen", "login", "--out", link])
    check(rc == 2 and "symlink" in err, "an --out that is a symlink → exit 2")
    rc, out, err = run([reg, "--url", "http://example.com/"], env={"PB_BROWSER_TRACE": os.path.join(d, "t")})
    check(rc == 2 and not os.path.exists(os.path.join(d, "t")) and procs(mark) == [],
          "…and the non-loopback --url never launched a browser or booted a server")

    print("no Playwright → exit 3, and no server was booted for it")
    runner = ("import sys, runpy; sys.modules['playwright'] = None; sys.argv = ['shot.py', %r, '--screen', 'login']; "
              "runpy.run_path(%r, run_name='__main__')" % (reg, SHOT))
    r = subprocess.run([sys.executable, "-c", runner], capture_output=True, text=True, timeout=60)
    check(r.returncode == 3 and "cannot run: Playwright not installed" in r.stdout, "exit 3 with the install hint (rc=%s)" % r.returncode)
    check(procs(mark) == [], "…having booted nothing")

    print("helpers")
    check(shot.parse_viewport("1440x900") == (1440, 900) and shot.parse_viewport(" 390X844 ") == (390, 844), "viewports parse (case and spaces forgiven)")
    p = shot.out_paths("/p", "login", [(1440, 900), (390, 844)])
    check(p == {"1440x900": "/p/.preview/shots/login-1440x900.png", "390x844": "/p/.preview/shots/login-390x844.png"},
          "the default output is <project>/.preview/shots/<name>-<WxH>.png")
    p = shot.out_paths("/p", "login", [(1440, 900)], "/x/me.png")
    check(p == {"1440x900": "/x/me.png"}, "--out FILE.png with one viewport is exactly that file")
    p = shot.out_paths("/p", "login", [(1440, 900), (390, 844)], "/x/me.png")
    check(p == {"1440x900": "/x/me-1440x900.png", "390x844": "/x/me-390x844.png"}, "…and with several, -<WxH> goes before the extension")
    check(shot._slug("/explore/card/opt-1?embed=1") == "explore-card-opt-1-embed-1" and shot._slug("../..") == "page",
          "a screen / path becomes a safe file name")


def browser_half():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print("  – skipped: Playwright is not installed (pip install playwright && playwright install chromium)")
        return
    reg, d = project()
    mark = os.path.basename(d)
    trace = os.path.join(d, "trace.txt")
    env = {"PB_BROWSER_TRACE": trace}

    print("a screen at two viewports — no preview running, so one is booted for the run")
    rc, out, err = run([reg, "--screen", "dashboard", "--role", "admin"], cwd=d, env=env)
    lines = out.splitlines()
    want = [os.path.join(d, ".preview", "shots", "dashboard-%s.png" % v) for v in ("1440x900", "390x844")]
    check(rc == 0 and lines == want, "exit 0, and it prints one path per PNG (rc=%s, %s)" % (rc, lines))
    check([png_size(p) for p in want] == [(1440, 900), (390, 844)], "…each a real PNG at exactly its viewport's size")
    with open(trace, encoding="utf-8") as f:
        check(len(f.read().splitlines()) == 1, "two viewports, ONE browser launch")
    check(wait_gone(lambda: procs(mark)), "the preview it booted is stopped again")

    print("with the project's preview running — reused, never a second one")
    rec = explore._start_server(reg)
    STARTED.append(rec["pid"])
    try:
        url = rec["url"].rstrip("/") + "/"
        os.remove(trace)
        rc, out, err = run([reg, "--screen", "login", "--viewport", "600x400", "--out", os.path.join(d, "shots-a")], cwd=d, env=env)
        check(rc == 0 and out.splitlines() == ["reusing the running preview at " + url, os.path.join(d, "shots-a", "login-600x400.png")],
              "it says it is reusing the preview, then prints the path (%s)" % out.splitlines())
        check(len(procs(mark)) == 1, "…and no second serve.py ran")
        rc, out, err = run([reg, "--screen", "login", "--viewport", "600x400", "--isolated", "--out", os.path.join(d, "shots-b")], cwd=d, env=env)
        check(rc == 0 and "reusing" not in out and len(procs(mark)) == 1, "--isolated boots its own for the run and stops it (the preview is still the only one left)")

        print("the options")
        rc, out, err = run([reg, "--screen", "dashboard", "--role", "admin", "--viewport", "700x500", "--out", os.path.join(d, "one.png"),
                            "--eval", "state.protoScreenId", "--wait-for", "#proto-frame", "--wait", "50"], cwd=d, env=env)
        l = [x for x in out.splitlines() if not x.startswith("reusing")]
        check(rc == 0 and l == [os.path.join(d, "one.png"), 'eval 700x500 "dashboard"'] and png_size(os.path.join(d, "one.png")) == (700, 500),
              "--out FILE.png, --eval prints `eval <WxH> <json>` (%s)" % l)
        rc, out, err = run([reg, "--screen", "dashboard", "--viewport", "700x500", "--full-page", "--out", os.path.join(d, "full.png")], cwd=d)
        size = png_size(os.path.join(d, "full.png"))
        check(rc == 0 and size and size[0] == 700, "--full-page writes the whole page (%s)" % (size,))
        rc, out, err = run([reg, "--screen", "dashboard", "--viewport", "700x500", "--selector", "#proto-frame", "--out", os.path.join(d, "el.png")], cwd=d)
        size = png_size(os.path.join(d, "el.png"))
        check(rc == 0 and size and size[0] <= 700 and size != (700, 500), "--selector screenshots just that element (%s)" % (size,))
        rc, out, err = run([reg, "--screen", "dashboard", "--viewport", "700x500", "--click", "#proto-frame", "--role", "admin",
                            "--eval", "state.protoScreenId", "--out", os.path.join(d, "click.png")], cwd=d)
        check(rc == 0 and 'eval 700x500 "dashboard"' in out, "--click and --role run before the look")
        rc, out, err = run([reg, "--path", "/design-system", "--viewport", "700x500", "--out", os.path.join(d, "ds.png")], cwd=d)
        check(rc == 0 and png_size(os.path.join(d, "ds.png")) == (700, 500), "--path /design-system looks at another page of the same preview")
        rc, out, err = run([reg, "--url", url, "--viewport", "700x500", "--out", os.path.join(d, "u.png")], cwd=d)
        check(rc == 0 and png_size(os.path.join(d, "u.png")) == (700, 500) and "reusing" not in out, "--url on the loopback preview works (no registry needed to find it)")
        rc, out, err = run([reg, "--screen", "dashboard", "--viewport", "700x500", "--eval", "console.error('boom')", "--console",
                            "--out", os.path.join(d, "c.png")], cwd=d)
        check(rc == 1 and "console 700x500 boom" in out, "--console prints the page's console errors and exits 1 (rc=%s)" % rc)
        rc, out, err = run([reg, "--screen", "dashboard", "--viewport", "700x500", "--console", "--out", os.path.join(d, "c2.png")], cwd=d)
        console_lines = [x for x in out.splitlines() if x.startswith("console ")]
        check(rc == (1 if console_lines else 0), "…and exits 0 when the page logged none (%d error lines, rc=%s)" % (len(console_lines), rc))

        print("not found → exit 1, and no PNG pretends it was")
        rc, out, err = run([reg, "--screen", "no-such-screen", "--viewport", "600x400", "--out", os.path.join(d, "x")], cwd=d)
        check(rc == 1 and "S-SCREEN" in out and not os.path.exists(os.path.join(d, "x")), "an unknown screen → exit 1, S-SCREEN, nothing written")
        rc, out, err = run([reg, "--screen", "login", "--viewport", "600x400", "--click", "#no-such-button", "--out", os.path.join(d, "y")], cwd=d)
        check(rc == 1 and "S-SELECTOR" in out and not os.path.exists(os.path.join(d, "y")), "a --click that matches nothing → exit 1, S-SELECTOR")
        rc, out, err = run([reg, "--screen", "login", "--viewport", "600x400", "--selector", "#no-such-element", "--out", os.path.join(d, "z")], cwd=d)
        check(rc == 1 and "S-SELECTOR" in out and not os.path.exists(os.path.join(d, "z", "login-600x400.png")), "a --selector that matches nothing → exit 1")
        rc, out, err = run([reg, "--screen", "login", "--viewport", "600x400", "--role", "no-such-role", "--out", os.path.join(d, "w")], cwd=d)
        check(rc in (0, 1), "an unknown role is not a crash (rc=%s)" % rc)
        rc, out, err = run([reg, "--url", "http://127.0.0.1:1/", "--viewport", "600x400", "--out", os.path.join(d, "v")], cwd=d)
        check(rc == 3 and "cannot run" in out, "a loopback URL nothing answers at → exit 3 (rc=%s)" % rc)
    finally:
        try:
            os.kill(rec["pid"], signal.SIGTERM)
        except OSError:
            pass
        wait_gone(lambda: procs(mark))
    check(procs(mark) == [], "the preview this test started is stopped")


try:
    print("— stdlib half —")
    stdlib_half()
    print("— browser half —")
    browser_half()
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
print("\n✓ shot.py: loopback only, one browser for every viewport, the project's preview reused, nothing left running")
