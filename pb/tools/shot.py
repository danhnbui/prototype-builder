#!/usr/bin/env python3
"""
shot.py — look at the prototype: one command, no hand-written Playwright script.

An agent that wants to SEE a screen used to write a throwaway Playwright script, start serve.py in
the background and kill it afterwards — a browser and a server per look, left running when the script
forgot to clean up. This is that, once, through the same door every other pb browser uses:

  * it reuses THIS project's running preview (found through .preview/server.json and confirmed by
    /__pb_health), or boots a private one for the run and stops it — `--isolated` always boots one;
  * ONE browser launch serves every viewport (a fresh context each), through browser.py, so the
    machine-wide limit (PB_BROWSER_SLOTS, default 3 headless browsers) applies;
  * it gets to a screen the way test_run.py does for `test.start` (setProtoScreen) and sets the role
    the way `--roles` does (setProtoRole).

Usage:
  python3 shot.py [registry.json] (--screen ID | --path /explore/<id>/<slot> | --url URL)
                  [--viewport WxH]... [--full-page] [--selector CSS] [--click CSS]...
                  [--wait-for CSS] [--wait MS] [--role ID] [--eval JS] [--console]
                  [--out FILE_OR_DIR] [--isolated]

  --screen ID       a registry screen, in the prototype (`/`)
  --path PATH       a page on the preview server — e.g. /explore/<id>/<slot>?embed=1, /design-system
  --url URL         a page on this machine (http://127.0.0.1 or http://localhost only — this is a tool
                    for pb previews, not a browser)
  --viewport WxH    repeatable; default 1440x900 and 390x844
  --full-page       the whole scrollable page, not just the viewport
  --selector CSS    screenshot only the first element this matches
  --click CSS       repeatable: click each, in order, before looking
  --wait-for CSS    wait for this to be on the page (10s) · --wait MS: then wait this long
  --role ID         act as this meta.roles id (setProtoRole)
  --eval JS         evaluate an expression in the page and print its JSON result, per viewport
  --console         print the page's console errors, and exit 1 if there were any
  --out FILE_OR_DIR where the PNGs go — a directory, or a .png file (several viewports then get
                    -<WxH> before the extension). Default: <registry folder>/.preview/shots/<name>-<WxH>.png

Prints one line per PNG written — its path, nothing else on that line. `--eval` prints
`eval <WxH> <json>`; `--console` prints `console <WxH> <message>`.

Exit: 0 ok · 1 console errors under --console, or a screen / selector / role not found, or --eval
threw · 2 usage · 3 cannot run (no Playwright, no reachable preview, the browser would not start) —
the same meanings as test_run.py. Stdlib only; Playwright is imported lazily.
"""
import argparse
import importlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import browser as pbbrowser  # noqa: E402

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_CANNOT_RUN = 0, 1, 2, 3
DEFAULT_VIEWPORTS = ("1440x900", "390x844")
_VIEWPORT = re.compile(r"^(\d{2,5})x(\d{2,5})\Z")
_ARTIFACT_SLUG = re.compile(r"[^A-Za-z0-9._-]+")


def _usage(msg):
    print("ERROR [S-USAGE] shot.py: " + msg, file=sys.stderr)
    return EXIT_USAGE


def _cannot_run(msg):
    print("⚠ cannot run: " + msg)
    return EXIT_CANNOT_RUN


def parse_viewport(text):
    """'1440x900' → (1440, 900); ValueError for anything else (and for a side under 100 or over 8000)."""
    m = _VIEWPORT.match(text.strip().lower())
    if not m or not all(100 <= int(g) <= 8000 for g in m.groups()):
        raise ValueError("--viewport wants WIDTHxHEIGHT between 100 and 8000, e.g. 1440x900 (got %r)" % text)
    return int(m.group(1)), int(m.group(2))


def _slug(text, default="page"):
    return _ARTIFACT_SLUG.sub("-", text).strip("-.")[:60] or default


def out_paths(base_dir, name, viewports, out=None):
    """{ 'WxH': png path } for every viewport — and the directory it creates is the caller's to make.
    `out` is a directory (default <base_dir>/.preview/shots) or a *.png file."""
    labels = ["%dx%d" % v for v in viewports]
    if out and out.lower().endswith(".png"):
        stem = out[:-4]
        return {l: (out if len(labels) == 1 else "%s-%s.png" % (stem, l)) for l in labels}
    d = out or os.path.join(base_dir, ".preview", "shots")
    return {l: os.path.join(d, "%s-%s.png" % (name, l)) for l in labels}


def build_parser():
    ap = argparse.ArgumentParser(
        prog="shot.py",
        description="Screenshot / look at a screen of the prototype through the project's preview "
                    "(reused if running, else booted for the run). Exit 0 ok · 1 console errors or "
                    "something not found · 2 usage · 3 cannot run.")
    ap.add_argument("registry", nargs="?", default="registry.json", help="path to registry.json (default ./registry.json)")
    g = ap.add_argument_group("what to look at (exactly one)")
    g.add_argument("--screen", metavar="ID", help="a registry screen, shown in the prototype")
    g.add_argument("--path", metavar="PATH", help="a page on the preview server, e.g. /explore/<id>/<slot>")
    g.add_argument("--url", metavar="URL", help="an http://127.0.0.1 or http://localhost URL")
    ap.add_argument("--viewport", action="append", metavar="WxH", help="repeatable (default 1440x900 and 390x844)")
    ap.add_argument("--full-page", action="store_true", help="capture the whole scrollable page")
    ap.add_argument("--selector", metavar="CSS", help="screenshot only the first element matching this")
    ap.add_argument("--click", action="append", default=[], metavar="CSS", help="repeatable: click each, in order")
    ap.add_argument("--wait-for", dest="wait_for", metavar="CSS", help="wait for this selector (10s)")
    ap.add_argument("--wait", type=int, default=0, metavar="MS", help="then wait this many milliseconds")
    ap.add_argument("--role", metavar="ID", help="act as this meta.roles id")
    ap.add_argument("--eval", dest="eval_js", metavar="JS", help="evaluate in the page; print the JSON result")
    ap.add_argument("--console", action="store_true", help="print console errors; exit 1 if there are any")
    ap.add_argument("--out", metavar="FILE_OR_DIR", help="a directory, or a .png file")
    ap.add_argument("--isolated", action="store_true", help="boot a private preview even if this project's is running")
    return ap


def _validate(a):
    """→ (viewports, error message or None). Everything that can be refused WITHOUT a browser."""
    given = [a.screen, a.path, a.url]
    if sum(x is not None for x in given) != 1:
        return None, "give exactly one of --screen ID, --path /page, --url http://127.0.0.1:PORT/…"
    if a.url is not None and not pbbrowser.is_loopback_url(a.url):
        return None, ("--url must be an http:// URL on this machine (127.0.0.1 or localhost): this is a "
                      "tool for pb previews, not a browser (got %r)" % a.url)
    if a.path is not None and not (a.path.startswith("/") and not a.path.startswith("//")
                                   and "://" not in a.path and "\\" not in a.path):
        return None, "--path is a path on the preview server and starts with a single / (got %r)" % a.path
    if a.screen is not None and not a.screen.strip():
        return None, "--screen needs a screen id"
    if a.wait < 0 or a.wait > 60000:
        return None, "--wait is milliseconds, 0..60000"
    try:
        viewports = [parse_viewport(v) for v in (a.viewport or DEFAULT_VIEWPORTS)]
    except ValueError as e:
        return None, str(e)
    viewports = list(dict.fromkeys(viewports))
    if a.out and (os.path.islink(a.out) or (a.out.lower().endswith(".png") and os.path.isdir(a.out))):
        return None, "--out %r is a symlink or a directory named like a file" % a.out
    return viewports, None


def _goto(page, base, a):
    if a.screen is not None:
        page.goto(base, wait_until="domcontentloaded")
        page.wait_for_selector("#proto-frame", timeout=15000)
    elif a.path is not None:
        page.goto(base.rstrip("/") + a.path, wait_until="domcontentloaded")
    else:
        page.goto(a.url, wait_until="domcontentloaded")


def shoot(p, base, a, viewports, paths):
    """Drive the browser: → (exit code, [printed lines]). `base` is the preview's URL (None for --url)."""
    tr = importlib.import_module("test_run")
    lines, code = [], EXIT_OK
    try:
        browser = pbbrowser.open_browser(p, "shot")
    except Exception as e:                                           # noqa: BLE001
        return _cannot_run("could not launch Chromium (%s) — playwright install chromium" % e), lines
    try:
        for (w, h) in viewports:
            label = "%dx%d" % (w, h)
            ctx = browser.new_context(viewport={"width": w, "height": h})
            try:
                page = ctx.new_page()
                errors = []
                page.on("console", lambda m, errs=errors: errs.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e, errs=errors: errs.append(str(e)))
                try:
                    _goto(page, base, a)
                except Exception as e:                               # noqa: BLE001 — nothing answered
                    return _cannot_run("%s did not load (%s)" % (
                        a.url or ((base or "").rstrip("/") + (a.path or "/")), str(e).splitlines()[0][:160])), lines
                if a.role:
                    ok, detail = tr._apply_role(page, a.role)
                    if not ok:
                        print("ERROR [S-ROLE] %s: %s" % (label, detail))
                        code = EXIT_FAIL
                        continue
                if a.screen is not None:
                    page.evaluate("(id) => { if (typeof setProtoScreen === 'function') setProtoScreen(id); }", a.screen)
                    page.wait_for_timeout(80)
                    cur = page.evaluate("() => (typeof state!=='undefined' && state) ? state.protoScreenId : null")
                    if cur != a.screen:
                        print("ERROR [S-SCREEN] %s: screen %r is not showing (the shell is on %r) — no such screen, "
                              "or the active role cannot see it" % (label, a.screen, cur))
                        code = EXIT_FAIL
                        continue
                missing = None
                for sel in a.click:
                    try:
                        page.click(sel, timeout=5000)
                        page.wait_for_timeout(120)
                    except Exception:                                # noqa: BLE001
                        missing = ("--click", sel)
                        break
                if missing is None and a.wait_for:
                    try:
                        page.wait_for_selector(a.wait_for, timeout=10000)
                    except Exception:                                # noqa: BLE001
                        missing = ("--wait-for", a.wait_for)
                if missing:
                    print("ERROR [S-SELECTOR] %s: %s %r matched nothing on the page" % (label, missing[0], missing[1]))
                    code = EXIT_FAIL
                    continue
                if a.wait:
                    page.wait_for_timeout(a.wait)
                path = paths[label]
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                if os.path.islink(path):
                    print("ERROR [S-OUT] %s: %s is a symlink — refusing to write through it" % (label, path))
                    code = EXIT_FAIL
                    continue
                if a.selector:
                    loc = page.locator(a.selector)
                    if loc.count() == 0:
                        print("ERROR [S-SELECTOR] %s: --selector %r matched nothing on the page" % (label, a.selector))
                        code = EXIT_FAIL
                        continue
                    loc.first.screenshot(path=path)
                else:
                    page.screenshot(path=path, full_page=a.full_page)
                lines.append(path)
                print(path)
                if a.eval_js is not None:
                    try:
                        print("eval %s %s" % (label, json.dumps(page.evaluate(a.eval_js), ensure_ascii=False)))
                    except Exception as e:                           # noqa: BLE001
                        print("ERROR [S-EVAL] %s: %s" % (label, str(e).splitlines()[0][:200]))
                        code = EXIT_FAIL
                if a.console:
                    for m in errors:
                        print("console %s %s" % (label, " ".join(str(m).split())[:300]))
                    if errors:
                        code = EXIT_FAIL
            finally:
                ctx.close()
    finally:
        browser.close()
    return code, lines


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    viewports, err = _validate(a)
    if err:
        return _usage(err)
    reg_path = os.path.abspath(a.registry)
    base_dir = os.path.dirname(reg_path)
    needs_preview = a.url is None
    if needs_preview and not os.path.isfile(reg_path):
        print("ERROR [R-IO] %s: file not found" % reg_path, file=sys.stderr)
        return EXIT_USAGE

    name = _slug(a.screen if a.screen is not None else (a.path.split("?")[0] if a.path is not None else "page"))
    paths = out_paths(base_dir, name, viewports, os.path.abspath(a.out) if a.out else None)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return _cannot_run("Playwright not installed — pip install playwright && playwright install chromium")

    tr = importlib.import_module("test_run")
    with sync_playwright() as p:
        if not needs_preview:
            code, _ = shoot(p, None, a, viewports, paths)
            return code
        try:
            transport = tr._transport(reg_path, None, a.isolated)
            srv = transport.__enter__()
        except SystemExit:                                          # the private server never came up
            return _cannot_run("no preview is running for %s and a private one would not start" % reg_path)
        try:
            code, _ = shoot(p, srv.url, a, viewports, paths)
        finally:
            transport.__exit__(None, None, None)
        return code


if __name__ == "__main__":
    sys.exit(main())
