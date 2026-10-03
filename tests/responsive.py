#!/usr/bin/env python3
"""
responsive.py — a design answers the device frame it is shown in, and the tool fits a phone.

A prototype used to be designed once and stretched: render bodies style themselves inline (no
breakpoint fits in style=""), and the frames are <div>s in one document, so a @media rule answered
the BROWSER WINDOW — a 429px phone frame on a 1440px monitor matched `min-width: 1024px`. This pins
the fix and the rules around it:

  1. a screen's `styleSrc` sheet reaches both sites as one <style id="pb-product-css">, after
     product.css, and is not inlined into the registry blob
  2. in a 1440px window, the MOBILE frame resolves `@container pb-screen` as compact and the LAPTOP
     frame as expanded — for the sheet's own rule and for the r-* utilities
  3. a missing styleSrc fails the render closed (RenderError), like a missing renderSrc
  4. lint: R-STYLE-MEDIA (size @media), R-STYLE-SCOPE (unscoped selector), R-PX in a sheet but not in
     an @container prelude, R-STYLESRC, and R-RESPONSIVE for false / true-with-a-screen-that-never-
     adapts (null is /pb:build's question, so it stays silent — an older project's CI stays green)
  5. the React scaffold carries the same sheet (src/product.css) and a pb-screen root
  6. the tool at 390px: the design-system site does not scroll sideways, its tree folds behind a
     toggle; the prototype's clipped tab strip says so (is-clip-r) and the last tab is reachable

Usage:  .venv/bin/python tests/responsive.py
Exit:   0 = clean · 1 = a failure · 2 = Playwright/browser not available (skip)
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TPL = os.path.join(ROOT, "pb", "template")
GOLDEN = os.path.join(ROOT, "fixtures", "golden")

_fail = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _fail.append(msg)


def _load(stem, path):
    spec = importlib.util.spec_from_file_location(stem, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[stem] = m
    spec.loader.exec_module(m)
    return m


sys.path.insert(0, TOOLS)
render = _load("render", os.path.join(TOOLS, "render.py"))
lint = _load("lint_registry", os.path.join(TOOLS, "lint_registry.py"))
react = _load("render_react", os.path.join(TOOLS, "render_react.py"))

SHEET = """/* login: one column compact, a probe that names the size class */
.s-login { --probe-size: compact; }
@container pb-screen (min-width: 600px) { .s-login { --probe-size: medium; } }
@container pb-screen (min-width: 1024px) { .s-login { --probe-size: expanded; } }
"""
PROBES = ('<span class="r-compact" data-probe="c">c</span>'
          '<span class="r-expanded-up" data-probe="x">x</span>')


def make_project(tmp):
    proj = os.path.join(tmp, "proj")
    shutil.copytree(GOLDEN, proj)
    body_p = os.path.join(proj, "render", "screens", "login.js")
    body = open(body_p, encoding="utf-8").read()
    body = body.replace("return '<div style=", "return '<div class=\"s-login\" style=", 1)
    body = body.replace("+ '</div></div>';", "+ '" + PROBES + "</div></div>';", 1)
    assert 's-login' in body and 'data-probe' in body, "fixture body changed shape"
    open(body_p, "w", encoding="utf-8").write(body)
    os.makedirs(os.path.join(proj, "render", "styles"))
    open(os.path.join(proj, "render", "styles", "login.css"), "w", encoding="utf-8").write(SHEET)
    reg_p = os.path.join(proj, "registry.json")
    reg = json.load(open(reg_p, encoding="utf-8"))
    for s in reg["screens"]:
        if s["id"] == "login":
            s["styleSrc"] = "render/styles/login.css"
    reg["meta"]["devices"] = ["laptop", "mobile"]
    json.dump(reg, open(reg_p, "w", encoding="utf-8"), indent=2)
    return proj, reg_p


def codes(findings, code):
    return [f for f in findings if f.code == code]


def main():
    tmp = tempfile.mkdtemp(prefix="pb-responsive-")
    try:
        proj, reg_p = make_project(tmp)
        proto = os.path.join(proj, "prototype.html")
        ds = os.path.join(proj, "design-system.html")

        print("1 · the sheet reaches both sites")
        _, html, _ = render.render_file(reg_p, os.path.join(TPL, "prototype.html"), proto)
        render.render_ds_file(reg_p, os.path.join(TPL, "design-system.html"),
                              os.path.join(TPL, "runtime.js"), ds)
        dsh = open(ds, encoding="utf-8").read()
        check("pb-product-css" in html and "--probe-size: expanded" in html, "prototype carries the sheet")
        check("pb-product-css" in dsh and "--probe-size: expanded" in dsh, "design-system site carries the sheet")
        i_base, i_sheet = html.find("r-expanded-up"), html.find("--probe-size: compact")
        check(0 <= i_base < i_sheet, "product.css comes before the project's sheets")
        blob = html[html.find("/*__PB_REGISTRY_START__*/"):html.find("/*__PB_REGISTRY_END__*/")]
        check('"style"' not in blob, "the sheet text is not duplicated into the inlined registry")

        print("3 · a missing styleSrc fails closed")
        bad = json.load(open(reg_p, encoding="utf-8"))
        bad["screens"][0]["styleSrc"] = "render/styles/nope.css"
        try:
            render.load_bodies(bad, proj)
            check(False, "missing styleSrc raised RenderError")
        except render.RenderError as e:
            check("styleSrc not found" in str(e), "missing styleSrc raised RenderError")

        print("4 · lint")
        reg = json.load(open(reg_p, encoding="utf-8"))
        f = lint.check(reg, base_dir=proj)
        check(not codes(f, "R-STYLE-MEDIA") and not codes(f, "R-STYLE-SCOPE") and not codes(f, "R-STYLESRC"),
              "the clean sheet raises no style finding")
        check(not [x for x in codes(f, "R-PX") if "login" in x.where],
              "a px inside an @container prelude is not a raw px")
        check(not codes(f, "R-RESPONSIVE"),
              "responsive unset (an older project) is /pb:build's question, not a lint finding")
        reg["meta"]["responsive"] = False
        check(any("false" in x.msg for x in codes(lint.check(reg, base_dir=proj), "R-RESPONSIVE")),
              "responsive false with two size classes → R-RESPONSIVE")
        reg["meta"]["responsive"] = True
        rr = codes(lint.check(reg, base_dir=proj), "R-RESPONSIVE")
        flagged = {x.where.split("id=")[-1].strip("'") for x in rr}
        check("login" not in flagged and "dashboard" in flagged,
              f"responsive true flags the screens that never adapt, not login ({sorted(flagged)})")
        reg["meta"]["devices"] = ["laptop", "monitor"]
        check(not codes(lint.check(reg, base_dir=proj), "R-RESPONSIVE"), "one size class → nothing to ask")
        sheet_p = os.path.join(proj, "render", "styles", "login.css")
        open(sheet_p, "w", encoding="utf-8").write(
            "@media (min-width: 1024px) { .s-login { color: red; } }\n.card { padding: 12px; }\n")
        f = lint.check(reg, base_dir=proj)
        check(bool(codes(f, "R-STYLE-MEDIA")), "a size @media → R-STYLE-MEDIA")
        check(bool(codes(f, "R-STYLE-SCOPE")), "a selector outside .s-login → R-STYLE-SCOPE")
        check(any("12px" in x.msg for x in codes(f, "R-PX")), "a raw px in a declaration → R-PX")
        check(codes(lint.check(reg, strict=True, base_dir=proj), "R-STYLE-MEDIA")[0].severity == "ERROR",
              "R-STYLE-MEDIA is an error under --strict")
        os.remove(sheet_p)
        check(bool(codes(lint.check(reg, base_dir=proj), "R-STYLESRC")), "a missing sheet → R-STYLESRC")
        open(sheet_p, "w", encoding="utf-8").write(SHEET)

        print("5 · the React scaffold")
        out = os.path.join(tmp, "scaffold")
        react.emit(reg_p, out, screen="login")
        pcss = open(os.path.join(out, "src", "product.css"), encoding="utf-8").read()
        app = open(os.path.join(out, "src", "App.jsx"), encoding="utf-8").read()
        check("--probe-size: expanded" in pcss and "container: pb-screen" in pcss, "src/product.css carries the sheet")
        check("product.css" in app and "proto-screen" in app, "App imports it under a pb-screen root")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("SKIP (browser half): playwright not installed")
            return 2 if not _fail else 1

        def offline(pg):
            """The web font and the mermaid CDN are not under test; a slow network must not fail it."""
            pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("file:", "data:", "blob:")) else r.abort())
            return pg

        print("2 · the frame decides, not the window (1440px window)")
        with sync_playwright() as p:
            b = p.chromium.launch()
            for dev, want, shown in (("mobile", "compact", "c"), ("laptop", "expanded", "x")):
                pg = offline(b.new_page(viewport={"width": 1440, "height": 900}))
                pg.goto("file://" + proto + f"?screen=login&device={dev}")
                pg.wait_for_selector(".s-login")
                got = pg.evaluate("getComputedStyle(document.querySelector('.s-login')).getPropertyValue('--probe-size').trim()")
                vis = pg.evaluate("[...document.querySelectorAll('[data-probe]')].filter(e=>e.offsetParent!==null).map(e=>e.dataset.probe).join('')")
                check(got == want, f"{dev} frame: the sheet's container rule resolves {want!r} (got {got!r})")
                check(vis == shown, f"{dev} frame: only the {want} utility is shown (got {vis!r})")
                pg.close()

            print("6 · the tool at 390px")
            pg = offline(b.new_page(viewport={"width": 390, "height": 844}))
            pg.goto("file://" + ds)
            pg.wait_for_selector("#ds-nav-toggle")
            sw = pg.evaluate("document.documentElement.scrollWidth")
            check(sw <= 390, f"design-system site does not scroll sideways (scrollWidth {sw})")
            check(pg.is_visible("#ds-nav-toggle") and not pg.is_visible("#ds-nav"),
                  "its tree folds behind the toggle")
            pg.click("#ds-nav-toggle")
            check(pg.is_visible("#ds-nav"), "the toggle opens the tree")
            pg.click("#ds-nav .ds-item >> nth=1")
            pg.wait_for_timeout(100)
            check(not pg.is_visible("#ds-nav"), "picking a page folds it away")
            pg.close()
            pg = offline(b.new_page(viewport={"width": 1280, "height": 832}))
            pg.goto("file://" + ds)
            pg.wait_for_selector("#ds-nav")
            check(pg.is_visible("#ds-nav") and not pg.is_visible("#ds-nav-toggle"), "wide: the tree is a sidebar, no toggle")
            pg.close()

            pg = offline(b.new_page(viewport={"width": 390, "height": 844}))
            pg.goto("file://" + proto)
            pg.wait_for_selector("#meta-nav .pb-tabs")
            st = pg.evaluate("""(()=>{const t=document.querySelector('#meta-nav .pb-tabs');
                return {clip:t.scrollWidth>t.clientWidth, r:t.classList.contains('is-clip-r')}})()""")
            if st["clip"]:
                check(st["r"], "a clipped tab strip fades its right edge")
            pg.evaluate("[...document.querySelectorAll('#meta-nav .pb-tab')].pop().click()")
            pg.wait_for_timeout(200)
            box = pg.evaluate("""(()=>{const t=[...document.querySelectorAll('#meta-nav .pb-tab')].pop().getBoundingClientRect();
                return [t.left, t.right]})()""")
            check(box[0] >= 0 and box[1] <= 390, f"the active last tab is scrolled into view ({box})")
            check(pg.evaluate("document.documentElement.scrollWidth") <= 390, "the prototype does not scroll sideways")
            pg.close()
            b.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _fail:
        print(f"FAIL: {len(_fail)} check(s)")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
