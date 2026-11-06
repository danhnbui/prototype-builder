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
  5. (retired with the engineering hand-off: the React scaffold no longer exists)
  6. the tool at 390px: the design-system site does not scroll sideways, its tree folds behind a
     toggle; the prototype's clipped tab strip says so (is-clip-r) and the last tab is reachable
  7. every page at 390px: no tab or UX segment scrolls the page sideways, the stacked User Flow canvas is
     ≥ 300px wide (it was 0px), Content → Definitions fits, and the Data diagram's zoom controls are on
     screen at 1024x768 (the canvas fits the viewport instead of a fixed 620px)

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

            print("7 · every page at 390px: a stacked flow, no page-level sideways scroll")
            # a copy of the project with a glossary, so the Content → Definitions grid has cards to overflow with
            reg_c = json.load(open(reg_p, encoding="utf-8"))
            reg_c["content"] = {"populated": True, "strings": [], "terms": [
                {"id": f"t-{i}", "term": t, "definition": "one patient, one doctor, one time — and a definition long enough to wrap",
                 "aka": ["visit", "booking"], "avoid": ["session"]} for i, t in enumerate(("Appointment", "Slot", "No-show"))]}
            reg_c_p = os.path.join(proj, "registry_content.json")
            json.dump(reg_c, open(reg_c_p, "w", encoding="utf-8"), indent=2)
            proto_c = os.path.join(proj, "prototype_content.html")
            render.render_file(reg_c_p, os.path.join(TPL, "prototype.html"), proto_c)

            pg = offline(b.new_page(viewport={"width": 390, "height": 844}))
            pg.goto("file://" + proto_c)
            pg.wait_for_selector("#meta-nav .pb-tabs")
            wide = []

            def look(label):
                pg.wait_for_timeout(200)
                w = pg.evaluate("document.documentElement.scrollWidth")
                if w > 390:
                    wide.append(f"{label} ({w}px)")

            look("prototype")
            seen = ["prototype"]
            for tab in ("summary", "flow", "erd"):
                pg.click(f"[data-meta-view={tab}]")
                look(tab)
                seen.append(tab)
                if tab == "summary":
                    for sub in pg.evaluate("[...document.querySelectorAll('[data-sub]')].map(e=>e.dataset.sub)"):
                        pg.click(f"[data-sub={sub}]")
                        look(f"summary/{sub}")
                        seen.append(f"summary/{sub}")
                elif tab == "flow":
                    for seg in pg.evaluate("[...document.querySelectorAll('[data-ux-view]')].map(e=>e.dataset.uxView)"):
                        pg.click(f"[data-meta-view=flow]")
                        pg.click(f"[data-ux-view={seg}]")
                        look(f"flow/{seg}")
                        seen.append(f"flow/{seg}")
                elif tab == "erd":
                    for v in ("table", "diagram"):
                        pg.click(f"[data-erd-view={v}]")
                        look(f"erd/{v}")
                        seen.append(f"erd/{v}")
            check(not wide, f"no tab or UX segment scrolls the page sideways at 390px ({len(seen)} looked at; wide: {wide})")

            pg.click("[data-meta-view=flow]")
            pg.click("[data-ux-view=flow]")
            pg.wait_for_selector("#flow-canvas")
            box = pg.evaluate("""(()=>{const r=document.getElementById('flow-canvas').getBoundingClientRect();
                return {w:r.width,h:r.height,l:r.left,r:r.right}})()""")
            check(pg.is_visible("#flow-canvas") and box["w"] >= 300 and box["l"] >= 0 and box["r"] <= 390,
                  f"User Flow at 390px: the canvas is visible and ≥ 300px wide, not squeezed to a sliver ({box['w']:.0f}px)")

            pg.click("[data-ux-view=content]")
            pg.wait_for_selector(".ct-terms")
            ct = pg.evaluate("""(()=>{const g=document.querySelector('.ct-terms');
                const cards=[...g.querySelectorAll('.ct-term')].map(c=>c.getBoundingClientRect());
                return {n:cards.length, scroll:g.scrollWidth-g.clientWidth,
                        right:Math.max(...cards.map(c=>c.right)), page:document.documentElement.scrollWidth}})()""")
            check(ct["n"] >= 3 and ct["scroll"] <= 0 and ct["right"] <= 390 and ct["page"] <= 390,
                  f"Content → Definitions does not scroll sideways at 390px ({ct})")
            pg.close()

            print("7b · the Data diagram's zoom controls are on screen at 1024x768")
            pg = offline(b.new_page(viewport={"width": 1024, "height": 768}))
            pg.goto("file://" + proto_c)
            pg.wait_for_selector("#meta-nav .pb-tabs")
            pg.click("[data-meta-view=erd]")
            pg.click("[data-erd-view=diagram]")
            pg.wait_for_selector("#erd-canvas .flow-zoom-controls")
            z = pg.evaluate("""(()=>{const r=document.querySelector('#erd-canvas .flow-zoom-controls').getBoundingClientRect();
                const c=document.getElementById('erd-canvas').getBoundingClientRect();
                return {t:r.top,b:r.bottom,l:r.left,r:r.right,cb:c.bottom}})()""")
            check(0 <= z["t"] and z["b"] <= 768 and 0 <= z["l"] and z["r"] <= 1024,
                  f"ERD zoom controls sit inside the 1024x768 viewport (top {z['t']:.0f}, bottom {z['b']:.0f})")
            check(z["cb"] <= 768, f"the whole ERD canvas ends above the fold, so the page needs no scroll to reach it (bottom {z['cb']:.0f})")
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
