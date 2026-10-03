#!/usr/bin/env python3
"""
chrome_states.py — the tool's state layer, icon scale and accent rule, measured in a browser.

chrome.css carries ONE state layer (hover · :focus-visible · pressed · disabled), ONE icon scale
(16px glyphs, 20px in an icon-only control) and the rule that nothing is highlighted with a bar
down its left edge. Each of those used to be decided per component, which is how half the
controls ended up with no hover, a few with no visible focus, three different glyph sizes and
eighteen left accent borders. This walks the rendered pages and checks every control the tool
draws — never the product's (.pb-product) and never the device mock's (.proto-frame: those
buttons are Chrome's, drawn at Chrome's metrics).

  1. every visible button / [role=tab] / a[href] changes something under :hover AND under
     :focus-visible (forced through the DevTools protocol, transitions off — so it is the CSS
     rule that is measured, not a moment of an animation). The control that is already the
     selection, and a disabled one, are exempt from the hover half only.
  2. no visible tool glyph (a square-ish <svg> up to 48px) is smaller than 16px
  3. every icon-only control (no letter or digit in it) has an aria-label and a title
  4. no element outside the product draws a one-sided left border unless it is a hairline
     (1px, in --pb-hair / --pb-hair-2) — a structural divider, never an accent

Pages: the prototype rendered from the golden fixture — all four
tabs, the UX Design segments, and the Sandbox menu open — and the design-system site (a component
page and a foundations page).

Usage:  .venv/bin/python tests/chrome_states.py
Exit:   0 = clean · 1 = a failure · 2 = Playwright/browser not available (skip)
"""
import importlib.util
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TPL = os.path.join(ROOT, "pb", "template")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: playwright not installed (pip install playwright && playwright install chromium)")
    sys.exit(2)

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


render = _load("render", os.path.join(TOOLS, "render.py"))
REG = GOLDEN

# The tool's own controls: outside the product and outside the device mock.
OUTSIDE = ":not(.pb-product *):not(.pb-product):not(.proto-frame *)"

# Mark every visible tool control with a stable index the protocol can find again.
MARK_JS = """(sel) => {
  document.querySelectorAll('[data-pbst]').forEach(e => e.removeAttribute('data-pbst'));
  const vis = e => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'
      && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
  const out = [];
  document.querySelectorAll(sel).forEach((e, i) => {
    if (!vis(e)) return;
    e.setAttribute('data-pbst', String(i));
    const name = (e.getAttribute('aria-label') || '').trim();
    out.push({ i: String(i), tag: e.tagName.toLowerCase(), cls: (e.className && e.className.baseVal === undefined ? e.className : '') || '',
               text: (e.textContent || '').trim().slice(0, 40), label: name,
               title: (e.getAttribute('title') || '').trim(),
               disabled: e.matches(':disabled, [aria-disabled="true"], .is-disabled'),
               selected: e.matches('[aria-selected="true"], [aria-current]:not([aria-current="false"]), [aria-pressed="true"], .active, .is-active') });
  });
  return out;
}"""

STYLE_JS = """(i) => {
  const e = document.querySelector('[data-pbst="' + i + '"]'); if (!e) return null;
  const c = getComputedStyle(e);
  return ['color','backgroundColor','borderTopColor','borderBottomColor','borderLeftColor','boxShadow',
          'outlineStyle','outlineWidth','outlineColor','textDecorationLine','textDecorationColor','opacity',
          'fontWeight'].map(k => c[k]).join('|');
}"""


def node_id(cdp, i):
    root = cdp.send("DOM.getDocument", {"depth": 0})["root"]["nodeId"]
    return cdp.send("DOM.querySelector", {"nodeId": root, "selector": f'[data-pbst="{i}"]'})["nodeId"]


def sweep_states(page, cdp, where):
    """Every visible tool control must change under :hover and under :focus-visible."""
    page.mouse.move(8, 8)   # park the real pointer on the bar's name, or it hovers whatever it last clicked
    els = page.evaluate(MARK_JS, f"button{OUTSIDE}, [role=tab]{OUTSIDE}, a[href]{OUTSIDE}")
    no_hover, no_focus = [], []
    for el in els:
        nid = node_id(cdp, el["i"])
        if not nid:
            continue
        base = page.evaluate(STYLE_JS, el["i"])
        # A disabled control must NOT react to hover, and the one already selected has nothing left to
        # promise — it reads as selected. Both still owe a focus ring.
        if not el["disabled"] and not el["selected"]:
            cdp.send("CSS.forcePseudoState", {"nodeId": nid, "forcedPseudoClasses": ["hover"]})
            hov = page.evaluate(STYLE_JS, el["i"])
            if hov == base:
                no_hover.append(el)
        cdp.send("CSS.forcePseudoState", {"nodeId": nid, "forcedPseudoClasses": ["focus", "focus-visible"]})
        foc = page.evaluate(STYLE_JS, el["i"])
        if foc == base:
            no_focus.append(el)
        cdp.send("CSS.forcePseudoState", {"nodeId": nid, "forcedPseudoClasses": []})
    fmt = lambda xs: ", ".join(f"{x['tag']}.{str(x['cls']).split(' ')[0] or '-'}«{x['text'][:18]}»" for x in xs[:8])
    check(not no_hover, f"{where}: all {len(els)} controls change on :hover"
          + (f" — {len(no_hover)} do not: {fmt(no_hover)}" if no_hover else ""))
    check(not no_focus, f"{where}: all {len(els)} controls show :focus-visible"
          + (f" — {len(no_focus)} do not: {fmt(no_focus)}" if no_focus else ""))
    return els


def sweep_static(page, where):
    """Glyph size, icon-only names, left accent borders."""
    res = page.evaluate("""(outside) => {
      const vis = e => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
        return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'
          && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
      const desc = e => e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0]
        : (e.className && e.className.baseVal ? '.' + e.className.baseVal.split(' ')[0] : ''))
        + (e.parentElement ? ' in ' + e.parentElement.tagName.toLowerCase()
           + (typeof e.parentElement.className === 'string' && e.parentElement.className ? '.' + e.parentElement.className.split(' ')[0] : '') : '');
      // 2 · tool glyphs
      const small = [];
      document.querySelectorAll('svg' + outside).forEach(s => {
        if (!vis(s) || s.closest('.flow-canvas, .mermaid')) return;   // diagrams, not glyphs
        const r = s.getBoundingClientRect();
        if (r.width > 48 || r.height > 48) return;               // a diagram, not a glyph
        const ar = r.width / r.height;
        if (ar > 2 || ar < 0.5) return;                          // notation (a crow's foot), not a glyph
        if (Math.min(r.width, r.height) < 15.5) small.push(desc(s) + ' ' + Math.round(r.width) + '×' + Math.round(r.height));
      });
      // 3 · icon-only controls
      const nameless = [];
      document.querySelectorAll('button' + outside + ', [role=tab]' + outside + ', a[href]' + outside).forEach(b => {
        if (!vis(b)) return;
        if (/[\\p{L}\\p{N}]/u.test(b.textContent || '')) return;  // it has words: not icon-only
        const label = (b.getAttribute('aria-label') || '').trim() || (b.getAttribute('aria-labelledby') ? 'by' : '');
        const title = (b.getAttribute('title') || '').trim();
        if (!label || !title) nameless.push(desc(b) + (label ? ' (no title)' : title ? ' (no aria-label)' : ' (neither)'));
      });
      // 4 · left accent borders — on elements and on their ::before / ::after
      const probe = document.createElement('div'); document.body.appendChild(probe);
      const hairs = [];
      for (const scheme of ['light', 'dark']) for (const v of ['--pb-hair', '--pb-hair-2']) {
        probe.style.colorScheme = scheme; probe.style.color = 'var(' + v + ')'; hairs.push(getComputedStyle(probe).color);
      }
      probe.remove();
      const accents = [];
      const all = document.querySelectorAll('body *' + outside);
      for (const e of all) {
        if (!vis(e)) continue;
        for (const pseudo of [null, '::before', '::after']) {
          const c = getComputedStyle(e, pseudo);
          if (pseudo && (c.content === 'none' || c.content === 'normal')) continue;
          const w = parseFloat(c.borderLeftWidth);
          if (!(w > 0) || c.borderLeftStyle === 'none') continue;
          const uniform = c.borderLeftWidth === c.borderRightWidth && c.borderLeftColor === c.borderRightColor
            && c.borderLeftStyle === c.borderRightStyle;
          if (uniform) continue;                                  // a box, not a left edge
          // a hairline divider is allowed — but it has to BE one: 1px, in a hairline colour (either
          // half of the pair: inside a light island a hairline resolves to its light value).
          const ok = w <= 1 && hairs.indexOf(c.borderLeftColor) !== -1;
          if (!ok) accents.push(desc(e) + (pseudo || '') + ' ' + c.borderLeftWidth + ' ' + c.borderLeftColor);
        }
      }
      return { small, nameless, accents };
    }""", OUTSIDE)
    check(not res["small"], f"{where}: no tool glyph under 16px" + (f" — {res['small'][:8]}" if res["small"] else ""))
    check(not res["nameless"], f"{where}: every icon-only control has an aria-label and a title"
          + (f" — {res['nameless'][:8]}" if res["nameless"] else ""))
    check(not res["accents"], f"{where}: no left accent border outside the product"
          + (f" — {res['accents'][:8]}" if res["accents"] else ""))


def block_network(ctx):
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("file:", "data:", "blob:")) else r.abort())


NO_MOTION = "*,*::before,*::after{transition:none!important;animation:none!important}"

print(f"0 · render {os.path.relpath(REG, os.path.dirname(ROOT))}")
with tempfile.TemporaryDirectory() as d:
    proto = os.path.join(d, "p.html")
    ds = os.path.join(d, "ds.html")
    render.render_file(REG, os.path.join(TPL, "prototype.html"), proto)
    render.render_ds_file(REG, os.path.join(TPL, "design-system.html"), os.path.join(TPL, "runtime.js"), ds)
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch()
    except Exception as e:  # noqa: BLE001 — no browser binary is a skip, not a failure
        print(f"SKIP: chromium not available ({e})")
        sys.exit(2)
    try:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        block_network(ctx)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        cdp = ctx.new_cdp_session(page)
        cdp.send("DOM.enable"); cdp.send("CSS.enable")

        print("1 · prototype — every tab")
        page.goto("file://" + proto, wait_until="domcontentloaded")
        page.wait_for_selector(".meta-tab", timeout=10000)
        page.add_style_tag(content=NO_MOTION)
        tabs = page.locator(".meta-tab")
        for t in range(tabs.count()):
            tabs.nth(t).click(); page.wait_for_timeout(150)
            name = (tabs.nth(t).text_content() or "").strip()
            sweep_states(page, cdp, name)
            sweep_static(page, name)
            # UX Design: walk its segments (each draws a different body)
            segs = page.locator(".meta-subtabs:not(.meta-subtabs--view) .meta-subtab")
            if name.startswith("UX") and segs.count() > 1:
                for k in range(1, segs.count()):
                    segs.nth(k).click(); page.wait_for_timeout(150)
                    sn = f"{name} › {(segs.nth(k).text_content() or '').strip()}"
                    sweep_states(page, cdp, sn)
                    sweep_static(page, sn)

        print("2 · prototype — the Sandbox menu, open")
        tabs.nth(0).click(); page.wait_for_timeout(150)
        page.click(".meta-sandbox"); page.wait_for_selector(".proto-sandbox-menu.is-visible, .proto-sandbox-menu", timeout=5000)
        page.wait_for_timeout(100)
        sweep_states(page, cdp, "Sandbox menu")
        sweep_static(page, "Sandbox menu")
        page.keyboard.press("Escape")

        print("3 · design-system site")
        page.goto("file://" + ds, wait_until="domcontentloaded")
        page.wait_for_selector(".cmp", state="attached", timeout=10000)
        page.add_style_tag(content=NO_MOTION)
        sweep_states(page, cdp, "DS component page")
        sweep_static(page, "DS component page")
        page.evaluate("location.hash = '#/f/colour'"); page.wait_for_timeout(150)
        sweep_states(page, cdp, "DS foundations page")
        sweep_static(page, "DS foundations page")

        check(not errs, f"zero page errors ({errs[:3]})")
    finally:
        browser.close()
        pw.stop()

print()
if _fail:
    print(f"✗ {len(_fail)} chrome-state failure(s).")
    sys.exit(1)
print("✓ chrome states clean.")
