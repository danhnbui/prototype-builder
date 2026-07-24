#!/usr/bin/env python3
"""
r5_ds_site.py — the design-system site acceptance (the two-sites refit).

One registry → two projections. This asserts the SECOND projection (the component workbench
served at /design-system): render design-system.html from the golden and verify it live-renders
every component, auto-detects interactivity (a live demo vs. grid-only), enumerates variant grids,
shows token foundations, and carries a per-component push-to-figma node JSON — plus the runtime
drift-guard (runtime.js stays in sync with the shell) and that serve.py serves BOTH routes.

The browser pass (Playwright, skipped if absent) drives the rendered page.

Usage:  python3 tests/r5_ds_site.py
Exit:   0 = clean · 1 = a regression
"""
import importlib.util
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TPL = os.path.join(ROOT, "pb", "template")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")
DS_SHELL = os.path.join(TPL, "design-system.html")
RUNTIME = os.path.join(TPL, "runtime.js")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def _load(stem, path):
    spec = importlib.util.spec_from_file_location(stem, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[stem] = m
    spec.loader.exec_module(m)
    return m


render = _load("render", os.path.join(TOOLS, "render.py"))
REG = json.load(open(GOLDEN, encoding="utf-8"))
COMP_IDS = [c["id"] for c in REG["components"]]

print("1 · render design-system.html from the golden")
with tempfile.TemporaryDirectory() as d:
    out = os.path.join(d, "design-system.html")
    reg, html, missing = render.render_ds_file(GOLDEN, DS_SHELL, RUNTIME, out)
    si = html.find("<script>")
    check(html.find('window["renderCmpButton"]') > si > 0, "emits window[renderCmp*] inside the <script>")
    check(html.find("function pbResolveTokens") > si, "shared runtime injected inside the <script>")
    check("/*__PB_RUNTIME__*/" not in html and "/*__PB_RENDER_FNS__*/" not in html,
          "runtime + render-fn markers consumed (nothing left unreplaced)")
    m = re.search(r"/\*__PB_NODES_START__\*/(.*?)/\*__PB_NODES_END__\*/", html, re.S)
    check(m is not None, "PB_NODES block present")
    if m:
        nodes = json.loads(m.group(1))
        check(all(cid in nodes for cid in COMP_IDS), "a push node exists for every component")
    check("/design-system" in html, "site links to the /design-system route")

print("2 · runtime drift-guard (runtime.js in sync with the shell)")
rt = open(RUNTIME, encoding="utf-8").read()
shell = open(os.path.join(TPL, "prototype.html"), encoding="utf-8").read()
for snippet in ("var ref = v.slice(1, -1).split('.').join('-');",
                "el.style.background = c ? 'var(--color-brand-primary)' : 'var(--color-bg-surface)';",
                "var idx = Array.prototype.indexOf.call(th.parentNode.children, th);"):
    check(snippet in rt and snippet in shell, "in sync: %s…" % snippet[:34])

print("3 · serve.py renders BOTH routes from the one registry")
serve = _load("serve", os.path.join(TOOLS, "serve.py"))
st = serve.State(os.path.abspath(GOLDEN), os.path.join(TPL, "prototype.html"),
                 os.path.join(tempfile.gettempdir(), "pb-r5.html"), False, DS_SHELL, RUNTIME)
ph, pe = serve.render_current(st)
dh, de = serve.render_ds_current(st)
check(pe is None and ph and "['erd'" in ph and "['handoff'" not in ph, "/ renders the prototype (4 tabs, no UI Design)")
check(de is None and dh and 'window["renderCmpButton"]' in dh, "/design-system renders the component workbench")

# 4 · browser pass (optional)
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("4 · browser pass — SKIPPED (playwright not installed)")
else:
    print("4 · browser pass")
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "design-system.html")
        render.render_ds_file(GOLDEN, DS_SHELL, RUNTIME, out)
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            errs = []
            pg.on("console", lambda mm: errs.append(mm.text) if mm.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto("file://" + out, wait_until="domcontentloaded")
            pg.wait_for_selector(".cmp", timeout=10000)
            data = pg.evaluate("""() => {
              const c = [].slice.call(document.querySelectorAll('.cmp'));
              const byId = {};
              c.forEach(x => { byId[x.querySelector('.id').textContent] = {
                demo: !!x.querySelector('.stage'), cells: x.querySelectorAll('.grid .cell').length,
                push: !!x.querySelector('.push') }; });
              return { count: c.length, byId,
                tokens: document.querySelectorAll('.tok-grid .tok').length,
                apostrophe: /User's Login Card/.test(document.body.textContent) };
            }""")
            check(data["count"] == len(COMP_IDS), "all %d components render (got %d)" % (len(COMP_IDS), data["count"]))
            btn = data["byId"].get("button", {})
            check(btn.get("demo") and btn.get("cells", 0) >= 2, "interactive button → live demo + variant grid")
            head = data["byId"].get("heading", {})
            check((not head.get("demo")) and head.get("cells", 0) >= 1, "non-interactive heading → grid-only (no demo)")
            check(data["tokens"] >= 10, "token foundations render (%d swatches)" % data["tokens"])
            check(data["apostrophe"], "apostrophe-named component (User's Login Card) renders")
            pg.click(".push")
            opened = pg.evaluate("() => { const dl=document.getElementById('pushdlg'); const o=dl&&dl.open; if(dl)dl.close(); return o; }")
            check(opened, "Push-to-Figma dialog opens with node JSON")
            check(not errs, "zero console errors (%r)" % errs)
            pg.close()
            b.close()

print()
if fails:
    print("✗ %d R5 ds-site check(s) failed" % len(fails))
    sys.exit(1)
print("✓ R5 ds-site clean")
