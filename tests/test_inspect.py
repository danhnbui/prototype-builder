#!/usr/bin/env python3
"""
test_inspect.py — Playwright test for the Prototype ⌥-hover inspect feature.

Boots the golden through serve.py and verifies: ⌥-hover shows the inspect label with the
element's structured id path; ⌥-click copies (toast) WITHOUT navigating; a normal click still
navigates (zero regression); a non-tagged element still yields a screen-scoped fallback path.
Spacing mode toggles, draws value chips for a padded element (and a free-space band where a box
is bigger than its children), ends on Esc / M / leaving the tab, and never blocks a click.

Usage:  python3 tests/test_inspect.py
Exit:   0 = all passed · 1 = a failure · 2 = Playwright/browser not available
"""
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVE = os.path.join(ROOT, "pb", "tools", "serve.py")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")

_failures = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _failures.append(msg)


class Server:
    def __init__(self, registry):
        self.registry = registry
        self.proc = None
        self.url = None

    def __enter__(self):
        self.proc = subprocess.Popen(
            [sys.executable, SERVE, self.registry, "--no-open", "--host", "127.0.0.1"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        deadline = time.time() + 15
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                break
            m = re.search(r"(http://127\.0\.0\.1:\d+/)", line)
            if m:
                self.url = m.group(1)
                break
        if not self.url:
            raise RuntimeError("serve.py did not report a preview URL")
        return self

    def __exit__(self, *exc):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def center(box):
    return (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def _offline(page):
    """Block every request that is not the local preview server.

    The shell pulls Mermaid from a CDN with a blocking <script> in <head>, so DOMContentLoaded
    waits on the network. Run four browser tests in one sweep and several Chromium instances
    hit that CDN at once; one eventually loses and page.goto times out at 30s — a red suite
    caused by the weather, not by pb. Nothing in these tests asserts on a rendered diagram
    (test_sandbox already filters mermaid console noise), so the honest fix is to stop
    depending on the network at all.
    """
    CT = {"script": "application/javascript", "stylesheet": "text/css",
          "font": "font/woff2", "image": "image/png"}

    def _handle(route):
        url = route.request.url
        if "127.0.0.1" in url or "localhost" in url:
            return route.continue_()
        # FULFIL empty, never abort. An aborted request logs "net::ERR_FAILED" to the console,
        # and these tests assert zero console errors — swapping a rare network flake for a
        # guaranteed failure is not a fix. An empty 200 loads cleanly and defines nothing.
        return route.fulfill(status=200, body="",
                             content_type=CT.get(route.request.resource_type, "text/plain"))

    page.route("**/*", _handle)


def run():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed — skipping (dev/CI-only dependency).")
        print("  pip install playwright && playwright install chromium")
        sys.exit(2)

    print("inspect (⌥-hover) on the golden:")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            print(f"Could not launch Chromium ({e}). Run: playwright install chromium")
            sys.exit(2)
        with Server(GOLDEN) as srv:
            page = browser.new_page(viewport={"width": 1366, "height": 820})
            _offline(page)
            page.goto(srv.url, wait_until="domcontentloaded")
            page.wait_for_selector(".meta-tab", timeout=10000)
            page.click(".meta-tab >> nth=0")  # Prototype
            page.wait_for_timeout(200)

            submit = page.locator('#proto-frame [data-handoff-el="submit"]')
            check(submit.count() >= 1, "found the tagged submit element to inspect")

            # ⌥-hover: move over the element (sets last-hover), then hold Alt (keydown shows overlay).
            cx, cy = center(submit.bounding_box())
            page.mouse.move(cx, cy)
            page.wait_for_timeout(60)
            page.keyboard.down("Alt")
            page.wait_for_timeout(120)
            label = page.locator("#pb-inspect-label")
            check(label.is_visible(), "⌥-hover shows the inspect label")
            txt = label.inner_text()
            check("screen:login › element:submit" in txt,
                  f"label shows the structured id path (got: {txt!r})")
            page.keyboard.up("Alt")
            page.wait_for_timeout(60)

            # ⌥-click copies (toast) and does NOT navigate.
            before = page.evaluate("() => state.protoScreenId")
            page.click('#proto-frame [data-handoff-el="submit"]', modifiers=["Alt"])
            page.wait_for_timeout(150)
            after = page.evaluate("() => state.protoScreenId")
            check(after == before == "login", f"⌥-click did not navigate (screen {before!r}->{after!r})")
            # "Copied" is the TOOL talking (not the product's own data-toast), so it is the tool's toast
            # (#pb-ui-toast, bottom-right) — and it names the reference that was copied.
            check(page.locator('#pb-ui-toast.is-on', has_text="Copied").count() >= 1
                  and page.locator('.proto-toast', has_text="Copied").count() == 0,
                  "⌥-click shows a 'Copied' toast — the tool's, not the product's")

            # A normal (no-Alt) valid submit STILL navigates — zero runtime regression.
            inp = page.locator('#proto-frame .field__input')
            inp.nth(0).fill("ada@example.com")
            inp.nth(1).fill("hunter2hunter2")
            page.click('#proto-frame [data-action="submit"]')
            # Wait for the STATE, not a fixed 220ms. The golden's submit navigates on a timer
            # (data-redirect-ms), so under a loaded machine — the full sweep, not this file on
            # its own — the evaluate could land mid-transition and come back "Execution context
            # was destroyed". wait_for_function retries across that instead of racing it.
            try:
                page.wait_for_function("() => state.protoScreenId === 'dashboard'", timeout=5000)
                landed = "dashboard"
            except Exception:
                landed = page.evaluate("() => state.protoScreenId")
            check(landed == "dashboard",
                  f"a normal submit still navigates (no inspect regression) (got {landed!r})")

            # Non-tagged element -> a screen-scoped fallback path still appears.
            page.evaluate("() => setProtoScreen('login')")
            page.wait_for_timeout(150)
            title = page.locator("#proto-frame h1")
            if title.count():
                tx, ty = center(title.bounding_box())
                page.mouse.move(tx, ty)
                page.wait_for_timeout(50)
                page.keyboard.down("Alt")
                page.wait_for_timeout(120)
                ftxt = page.locator("#pb-inspect-label").inner_text()
                check("screen:login" in ftxt, f"non-tagged element still yields a path (got: {ftxt!r})")
                page.keyboard.up("Alt")

            # Pick mode: the bar's cursor button keeps inspect on with no ⌥, and a click copies the
            # COMPONENT's name — and only copies: no navigation, no submit.
            page.evaluate("() => setProtoScreen('login')")
            page.wait_for_timeout(150)
            page.evaluate("""() => { window.__copied = []; const o = copyCommandToClipboard;
                copyCommandToClipboard = s => { window.__copied.push(s); return o(s); }; }""")
            pick = page.locator(".pb-bar-end .meta-pick")
            check(pick.count() == 1, "the bar carries one Pick button on the Prototype tab")
            search_box, pick_box = page.locator(".meta-search").bounding_box(), pick.bounding_box()
            check(pick_box and search_box and pick_box["x"] > search_box["x"], "Pick sits right after Search")
            pick.click()
            page.wait_for_timeout(80)
            check(pick.get_attribute("aria-pressed") == "true", "Pick is pressed once clicked")
            cmp_el = page.locator("#proto-frame [data-cmp]").first
            check(cmp_el.count() == 1, "the golden's login renders at least one component root (data-cmp)")
            cmp_id = cmp_el.get_attribute("data-cmp")
            bx, by = center(cmp_el.bounding_box())
            page.mouse.move(bx, by)
            page.wait_for_timeout(100)
            check(page.locator("#pb-inspect-label").is_visible(), "picking shows the label without holding ⌥")
            # The label never covers what it names (it used to sit 30px up but be taller than that), and
            # the tool's colour is its own, not the product's --brand.
            geo = page.evaluate("""() => { const b = document.getElementById('pb-inspect-box').getBoundingClientRect(),
                l = document.getElementById('pb-inspect-label').getBoundingClientRect(), cs = getComputedStyle(document.documentElement);
                const over = !(l.right <= b.left || l.left >= b.right || l.bottom <= b.top || l.top >= b.bottom);
                const on = l.left >= 0 && l.top >= 0 && l.right <= innerWidth && l.bottom <= innerHeight;
                const probe = document.createElement('i'); document.body.appendChild(probe);
                probe.style.color = 'var(--brand)'; const brand = getComputedStyle(probe).color; probe.remove();
                return { over, on, box: getComputedStyle(document.getElementById('pb-inspect-box')).borderTopColor, brand,
                         pick: cs.getPropertyValue('--pb-pick').trim() !== '' }; }""")
            check(not geo["over"] and geo["on"], f"the pick label sits outside the framed component, on screen ({geo})")
            check(geo["pick"] and geo["box"] != geo["brand"], f"the pick box is drawn in --pb-pick, not --brand ({geo})")
            # Every visible element of the screen: the label is outside its box unless the box fills the view.
            bad = page.evaluate("""() => { let bad = []; for (const el of document.querySelectorAll('#proto-frame .proto-screen *')) {
                const r = el.getBoundingClientRect(); if (r.width < 8 || r.height < 8 || r.bottom < 0 || r.top > innerHeight) continue;
                pbInspectShow(el); const b = document.getElementById('pb-inspect-box').getBoundingClientRect(),
                l = document.getElementById('pb-inspect-label').getBoundingClientRect();
                const fills = b.top - l.height - 6 < 0 && b.bottom + l.height + 6 > innerHeight;
                if (!fills && !(l.right <= b.left || l.left >= b.right || l.bottom <= b.top || l.top >= b.bottom)) bad.push(el.className || el.tagName);
                if (l.left < 0 || l.top < 0 || l.right > innerWidth || l.bottom > innerHeight) bad.push('offscreen:' + (el.className || el.tagName)); }
                return bad; }""")
            check(bad == [], f"no element's pick label covers its box or leaves the view ({bad[:5]})")
            page.mouse.move(bx + 1, by)
            page.mouse.move(bx, by)
            page.wait_for_timeout(60)
            before = page.evaluate("() => state.protoScreenId")
            page.mouse.click(bx, by)
            page.wait_for_timeout(150)
            copied = page.evaluate("() => window.__copied")
            want = page.evaluate("id => { const c = (PB_DATA.handoff.organisms || []).find(c => c.id === id)"
                                 " || pbOrgById()[id]; return (c && c.name) || id; }", cmp_id)
            # Since the any-element inspector a pick-click copies the FULL reference, not the bare component name.
            check(copied[-1:] == [f"Login › {want} (h1.pb-heading)"],
                  f"a pick-click copies the full reference 'Screen › Component (tag.class)' (got {copied!r})")
            check(page.evaluate("() => state.protoScreenId") == before, "a pick-click does not navigate")
            # The submit with valid fields WOULD navigate on a normal click; picked, it only copies.
            inp = page.locator('#proto-frame .field__input')
            inp.nth(0).evaluate("(el) => el.value = 'ada@example.com'")
            inp.nth(1).evaluate("(el) => el.value = 'hunter2hunter2'")
            page.click('#proto-frame [data-action="submit"]')
            page.wait_for_timeout(400)
            check(page.evaluate("() => state.protoScreenId") == "login"
                  and page.locator('.proto-toast').count() == 0,
                  f"a pick-click on a valid submit neither submits nor navigates (copied {copied[-1:]!r} then "
                  f"{page.evaluate('() => window.__copied')[-1:]!r})")
            # Pick names ANY element, not only the nearest component: a leaf text node inside a component
            # gives the component's name AND its own tag.class, a dashed box frames the component's root
            # next to the solid box on the element, and a click copies the full reference.
            page.wait_for_function("() => !window.pbPickNotice", timeout=3000)  # the earlier click's "Copied" has gone
            leaf = page.locator('#proto-frame [data-cmp="text-input"] label.field__label').first
            root = page.locator('#proto-frame [data-cmp="text-input"]').first
            lb, rb = leaf.bounding_box(), root.bounding_box()
            lx, ly = center(lb)
            page.mouse.move(lx + 1, ly)
            page.mouse.move(lx, ly)
            page.wait_for_timeout(100)
            ltxt = page.locator("#pb-inspect-label").inner_text()
            check("TextInput" in ltxt and "label.field__label" in ltxt,
                  f"hovering a leaf text node names its component AND its tag.class (got {ltxt!r})")
            check("local" in ltxt or "cobot DS" in ltxt, f"the label says where the component comes from (got {ltxt!r})")
            sbox = page.locator("#pb-inspect-box").bounding_box()
            cbox = page.locator("#pb-inspect-cmp").bounding_box() if page.locator("#pb-inspect-cmp").is_visible() else None
            check(abs(sbox["width"] - lb["width"]) < 2 and abs(sbox["height"] - lb["height"]) < 2,
                  f"the solid box is on the exact element, not the component ({sbox} vs {lb})")
            check(cbox is not None and abs(cbox["width"] - rb["width"]) < 2 and abs(cbox["height"] - rb["height"]) < 2,
                  f"a dashed box frames the component root when the element is not the root ({cbox} vs {rb})")
            page.mouse.click(lx, ly)
            page.wait_for_timeout(150)
            ref = page.evaluate("() => window.__copied.slice(-1)[0]")
            check(ref == "Login › TextInput (label.field__label)",
                  f"a click on that text copies the full reference (got {ref!r})")
            page.wait_for_function("() => !window.pbPickNotice", timeout=3000)
            # On the component's own root there is no second box; on a spot no component owns, the label says so.
            hx, hy = center(page.locator("#proto-frame h1[data-cmp]").bounding_box())
            page.mouse.move(hx + 1, hy)
            page.mouse.move(hx, hy)
            page.wait_for_timeout(100)
            check(not page.locator("#pb-inspect-cmp").is_visible(), "no dashed box when the element IS the component root")
            page.evaluate("() => { const f = document.querySelector('#proto-frame > div'); pbInspectShow(f); }")
            ptxt = page.locator("#pb-inspect-label").inner_text()
            check("no component" in ptxt and "div" in ptxt, f"an element no component owns says 'no component' with its tag (got {ptxt!r})")
            page.keyboard.press("Escape")
            page.wait_for_timeout(60)
            check(pick.get_attribute("aria-pressed") == "false"
                  and not page.locator("#pb-inspect-label").is_visible(), "Esc ends pick mode and hides the label")
            check(not page.locator("#pb-inspect-cmp").is_visible(), "Esc also hides the dashed component box")
            page.keyboard.press("i")
            page.wait_for_timeout(60)
            check(pick.get_attribute("aria-pressed") == "true", "I toggles pick mode on")
            page.click(".meta-tab >> nth=1")
            page.wait_for_timeout(150)
            check(page.evaluate("() => pbPickOn") is False and page.locator(".meta-pick").count() == 0,
                  "leaving the Prototype tab ends pick mode and drops the button")

            # Spacing mode: the bar's Spacing button (or M) outlines every element and, on hover, draws
            # the element's margin / padding / gap as bands with value chips. It never blocks a click.
            page.click(".meta-tab >> nth=0")
            page.wait_for_timeout(150)
            page.evaluate("() => setProtoScreen('login')")
            page.wait_for_timeout(150)
            sp = page.locator(".pb-bar-end .meta-spacing")
            check(sp.count() == 1, "the bar carries one Spacing button on the Prototype tab")
            pick_box, sp_box = page.locator(".meta-pick").bounding_box(), sp.bounding_box()
            check(pick_box and sp_box and sp_box["x"] > pick_box["x"], "Spacing sits right after Pick")
            check(sp.get_attribute("aria-pressed") == "false", "Spacing starts off")
            sp.click()
            page.wait_for_timeout(80)
            check(sp.get_attribute("aria-pressed") == "true"
                  and page.evaluate("() => document.body.classList.contains('pb-spacing')"),
                  "Spacing is pressed once clicked, and the body carries pb-spacing")
            # An element of the golden's login that has real padding (found, not assumed).
            pad = page.evaluate("""() => {
                const els = Array.from(document.querySelectorAll('#proto-frame *'));
                const hit = els.find(e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
                    return r.width > 20 && r.height > 10 && parseFloat(s.paddingTop) + parseFloat(s.paddingLeft) > 0; });
                if (!hit) return null;
                hit.setAttribute('data-sp-probe', ''); return true; }""")
            check(pad, "the golden's login has an element with padding to measure")
            if pad:
                # Aim at the element's own padding (just inside its top-left corner), so the pointer
                # lands on it and not on a child.
                pbox = page.locator('#proto-frame [data-sp-probe]').bounding_box()
                page.mouse.move(pbox["x"] + 5, pbox["y"] + 5)
                page.mouse.move(pbox["x"] + 1, pbox["y"] + 1)
                page.wait_for_timeout(150)
                nchips = page.locator("#pb-sp-layer .pb-sp-chip").count()
                check(nchips >= 1, f"hovering a padded element draws at least one value chip (got {nchips})")
                check(page.evaluate("() => getComputedStyle(document.getElementById('pb-sp-layer')).pointerEvents") == "none",
                      "the spacing overlay never takes the pointer")
            # Free space: a column flex box with min-height 40 centring a 28px child leaves 6 above and 6
            # below. That is not margin, padding or gap, so it is its own 'free' band (cyan, never grey).
            free = page.evaluate("""() => {
                const f = document.querySelector('#proto-frame .proto-screen') || document.getElementById('proto-frame'); const box = document.createElement('div');
                box.style.cssText = 'display:flex;flex-direction:column;justify-content:center;min-height:40px;width:200px';
                box.innerHTML = '<div style="height:28px"></div>'; f.appendChild(box);
                const bands = pbSpacingMeasure(box).filter(b => b[0] === 'free').map(b => [b[3], Math.round(b[2])]);
                const probe = document.createElement('div'); probe.className = 'pb-sp-chip--free';
                const layer = pbSpacingLayer(); layer.appendChild(probe); const bg = getComputedStyle(probe).backgroundColor; probe.remove();
                box.remove(); return { bands, bg }; }""")
            check(sorted(free["bands"]) == [["bottom", 6], ["top", 6]],
                  f"a min-height box centring a shorter child shows 6px free bands above and below (got {free['bands']})")
            check(free["bg"] == "rgb(14, 116, 144)", f"the free-space chip is cyan #0e7490, not grey (got {free['bg']})")
            # Spacing does not block the preview: a valid submit still navigates.
            inp = page.locator('#proto-frame .field__input')
            inp.nth(0).fill("ada@example.com")
            inp.nth(1).fill("hunter2hunter2")
            page.click('#proto-frame [data-action="submit"]')
            try:
                page.wait_for_function("() => state.protoScreenId === 'dashboard'", timeout=5000)
                landed = "dashboard"
            except Exception:
                landed = page.evaluate("() => state.protoScreenId")
            check(landed == "dashboard", f"a normal click under Spacing still acts and navigates (got {landed!r})")
            page.keyboard.press("Escape")
            page.wait_for_timeout(60)
            check(sp.get_attribute("aria-pressed") == "false"
                  and not page.evaluate("() => document.body.classList.contains('pb-spacing')")
                  and page.locator("#pb-sp-layer .pb-sp-chip").count() == 0,
                  "Esc ends Spacing, drops pb-spacing and clears the chips")
            page.keyboard.press("m")
            page.wait_for_timeout(60)
            check(sp.get_attribute("aria-pressed") == "true", "M toggles Spacing on")
            page.keyboard.press("m")
            page.wait_for_timeout(60)
            check(sp.get_attribute("aria-pressed") == "false", "M toggles Spacing off")
            page.keyboard.press("m")
            page.wait_for_timeout(60)
            page.click(".meta-tab >> nth=1")
            page.wait_for_timeout(150)
            check(page.evaluate("() => pbSpacingOn") is False and page.locator(".meta-spacing").count() == 0
                  and not page.evaluate("() => document.body.classList.contains('pb-spacing')"),
                  "leaving the Prototype tab ends Spacing and drops the button")

            # pbUse stamps data-cmp on the FIRST tag. A component whose HTML opens with its own <style> used
            # to be stamped on the <style> (which Pick skips), so every hover named the outermost component.
            # The stamp now goes to the first element after the leading <style>s; other output is unchanged.
            stamp = page.evaluate("""() => {
                const add = (id, html) => { window['renderCmp_' + id] = () => html;
                    PB_REGISTRY.components.push({ id, name: id, renderFn: 'renderCmp_' + id }); };
                add('st1', '<style>.st1{color:red}</style><div class="st1">hi</div>');
                add('st2', '\\n <style media="all">.a{}</style>\\n<style>.b{}</style>\\n  <section class="st2"><span>x</span></section>');
                add('st3', '<div class="st3">plain</div>');
                add('st4', '<style>.only{}</style>just text');
                PB_ORG_BY_ID_CACHE = null;
                return { st1: pbUse('st1'), st2: pbUse('st2'), st3: pbUse('st3'), st4: pbUse('st4') }; }""")
            check(stamp["st1"] == '<style>.st1{color:red}</style><div data-cmp="st1" class="st1">hi</div>',
                  f"a component starting with a <style> is stamped on its first element, not the <style> (got {stamp['st1']!r})")
            check('<style media="all">' in stamp["st2"] and "<style>.b{}</style>" in stamp["st2"]
                  and '<section data-cmp="st2" class="st2">' in stamp["st2"] and stamp["st2"].count("data-cmp") == 1,
                  f"several leading <style>s (with whitespace and attributes) are all skipped (got {stamp['st2']!r})")
            check(stamp["st3"] == '<div data-cmp="st3" class="st3">plain</div>',
                  f"a component not starting with a <style> is stamped exactly as before (got {stamp['st3']!r})")
            check(stamp["st4"].startswith("<style data-cmp=") and stamp["st4"].count("data-cmp") == 1,
                  f"a <style> with no element after it is left stamped as before (got {stamp['st4']!r})")
            page.close()
        browser.close()

    print()
    if _failures:
        print(f"✗ {len(_failures)} inspect assertion(s) failed.")
        sys.exit(1)
    print("✓ All inspect assertions passed.")


if __name__ == "__main__":
    run()
