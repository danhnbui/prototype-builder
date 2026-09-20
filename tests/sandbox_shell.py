#!/usr/bin/env python3
"""
sandbox_shell.py — the Prototype tab's own controls, driven in a real browser.

Everything the Sandbox menu offers acts on the page BEHIND the menu, which is why every bug
this file guards looked like "the button does nothing". None of them would have shown up in a
static read of the shell, and none of them were covered:

  1. Chrome · None      — PB_SHELL_OPTS offered a third option, PB_SHELLS mapped it, the CSS
                          styled it, and setProtoShell() still coerced anything that was not
                          'app' to 'browser'. Three of four layers agreed and the feature was
                          dead. The guard is the SETTER, not the option list.
  2. Structure tree     — the toggle lives inside a popover anchored over the exact strip the
                          panel slides into, so it opened invisibly; the next click in the
                          prototype then closed it again. Both halves are asserted.
  3. Compare            — two devices at once. The contract is that each frame lays out at its
                          TRUE css width and the pair shares ONE transform, so the size ratio
                          on screen is the real one. Per-frame fitting would pass a naive
                          "two frames render" test while destroying the only reason to look.
  4. Scenario testing   — the menu listed scenarios by `sc.title`, a field the authored shape
                          has never had, so every row read "scenario".
  5. Frame-scoped runtime — a second frame must not make the first frame's empty inputs fail
                          the second frame's submit.
  5b. Tablet chrome     — an iPad bezel wearing macOS traffic lights and an extensions button,
                          and the only device whose OS status bar came and went with the chrome
                          toggle. Plus a phone's Dynamic Island drawn on a tablet.
  6. In-page navigation — the half of navigation that never changes a screen: a scroll to a
                          section, and a handler that reads `closest` and `getElementById` in the
                          same breath. Both used to reach exactly one of the two frames, which
                          reads as "the content only showed up on one device".

Dev/CI-only dependency (NS4): pip install playwright && playwright install chromium

Usage:  python3 tests/sandbox_shell.py
Exit:   0 = all passed · 1 = a failure · 2 = Playwright/browser not available
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_smoke import GOLDEN, Server, _offline  # noqa: E402  (same harness, one definition)

# A screen with navigation that happens INSIDE the page — the golden has none, and in-page state
# is exactly what compare mode used to drop on the floor.
WIZARD_BODY = """function renderScreenWizard(props) {
  return '<div style="padding:24px;display:flex;flex-direction:column;gap:16px">'
    + '<div id="wiz" data-machine="wiz" data-step-initial="one">'
    +   '<section data-step-pane="one"><p>PANE ONE</p>'
    +     '<button data-step-go="two">Next</button></section>'
    +   '<section data-step-pane="two"><p>PANE TWO</p>'
    +     '<button data-step-go="one">Back</button></section>'
    + '</div>'
    + '<div class="field"><label>Password</label>'
    +   '<input class="field__input" type="password" data-required>'
    +   '<span data-action="toggle-password">Show</span></div>'
    + '<input id="flt" class="field__input" data-preserve placeholder="Filter">'
    + '<button data-action="submit">Submit</button>'
    + '</div>';
}
"""


# In-page navigation as a real project writes it: a tab bar that moves its own highlight with
# `closest` (frame-local) and swaps the content host by id (document-wide — always frame A), and
# sections you navigate to by scrolling. Neither shape changes the screen, so neither re-renders.
NAV_BODY = """function renderScreenNav(props) {
  return '<div style="padding:16px">'
    + '<nav id="tabbar">'
    +   '<button data-tab="a" class="active" onclick="pgGo(this,\\'a\\')">A</button>'
    +   '<button data-tab="b" onclick="pgGo(this,\\'b\\')">B</button>'
    +   '<a href="#sec3" id="jump">Jump to 3</a>'
    +   '<button id="btns" onclick="pgScroll()">Scroll to 3</button>'
    + '</nav>'
    + '<div id="tabhost"><p id="pane">PANE A</p></div>'
    + '<section id="sec1" style="height:700px">SEC 1</section>'
    + '<section id="sec2" style="height:700px">SEC 2</section>'
    + '<section id="sec3" style="height:700px">SEC 3</section>'
    + '<style>.vw{display:none}'
    +   '.vhost:has(#v1:checked) .vw1{display:block}'
    +   '.vhost:has(#v2:checked) .vw2{display:block}</style>'
    + '<div class="vhost">'
    +   '<input type="radio" name="vw" id="v1" checked style="position:absolute;opacity:0">'
    +   '<input type="radio" name="vw" id="v2" style="position:absolute;opacity:0">'
    +   '<label for="v1">one</label><label for="v2">two</label>'
    +   '<div class="vw vw1">VIEW ONE</div><div class="vw vw2">VIEW TWO</div>'
    + '</div>'
    + '</div>';
}
"""
NAV_RUNTIME = """function pgGo(el, k) {
  var bar = el.closest('#tabbar');
  Array.prototype.forEach.call(bar.querySelectorAll('[data-tab]'), function (b) {
    b.classList.toggle('active', b.getAttribute('data-tab') === k);
  });
  document.getElementById('tabhost').innerHTML = '<p id="pane">PANE ' + k.toUpperCase() + '</p>';
}
function pgScroll() { document.getElementById('sec3').scrollIntoView({ block: 'start' }); }
"""


def make_wizard_registry(tmpdir):
    """The golden plus two screens whose navigation stays on the page."""
    shutil.copytree(os.path.join(os.path.dirname(GOLDEN), "render"), os.path.join(tmpdir, "render"))
    for name, body in (("wizard.js", WIZARD_BODY), ("nav.js", NAV_BODY)):
        with open(os.path.join(tmpdir, "render", "screens", name), "w", encoding="utf-8") as f:
            f.write(body)
    os.makedirs(os.path.join(tmpdir, "runtime"), exist_ok=True)
    with open(os.path.join(tmpdir, "runtime", "pg.js"), "w", encoding="utf-8") as f:
        f.write(NAV_RUNTIME)
    reg = json.load(open(GOLDEN, encoding="utf-8"))
    reg["screens"].append({"id": "wizard", "name": "Wizard", "renderFn": "renderScreenWizard",
                           "renderSrc": "render/screens/wizard.js", "level": "page", "elements": []})
    reg["screens"].append({"id": "nav", "name": "Nav", "renderFn": "renderScreenNav",
                           "renderSrc": "render/screens/nav.js", "level": "page", "elements": []})
    reg["runtime"] = [{"id": "pg", "src": "runtime/pg.js"}]
    path = os.path.join(tmpdir, "registry.json")
    json.dump(reg, open(path, "w", encoding="utf-8"), indent=2)
    return path

_failures = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _failures.append(msg)


def run():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed — skipping (dev/CI-only dependency).")
        sys.exit(2)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            print(f"Chromium unavailable ({e}) — skipping.")
            sys.exit(2)

        with Server(GOLDEN) as srv:
            page = browser.new_page(viewport={"width": 1500, "height": 950})
            _offline(page)
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(srv.url, wait_until="domcontentloaded")
            page.wait_for_selector("#proto-frame", timeout=10000)

            def menu():
                page.evaluate("document.querySelectorAll('.copy-popover,.copy-popover-backdrop')"
                              ".forEach(e => e.remove())")
                page.click(".meta-sandbox")
                page.wait_for_selector(".proto-sandbox-menu.is-visible")

            print("1 · chrome: all three options reach state")
            for label, want, present, absent in [
                ("None", "none", None, ".proto-tabbar"),
                ("App", "app", ".proto-appbar", ".proto-tabbar"),
                ("Browser", "browser", ".proto-tabbar", ".proto-appbar"),
            ]:
                menu()
                page.click(f".proto-shell-toggle .proto-shell-btn:has-text('{label}')")
                page.wait_for_timeout(180)
                got = page.evaluate("state.protoShell")
                check(got == want, f"{label} → state.protoShell == {want!r} (got {got!r})")
                if present:
                    check(page.locator(present).count() == 1, f"  and {present} renders")
                check(page.locator(absent).count() == 0, f"  and {absent} does not")
            page.evaluate("document.querySelectorAll('.copy-popover,.copy-popover-backdrop')"
                          ".forEach(e => e.remove())")
            check("proto-shell--none" in page.evaluate(
                "(() => { setProtoShell('none'); renderPrototype();"
                " return document.getElementById('proto-frame-wrap').className; })()"),
                "the frame carries proto-shell--none, so the window flattens")
            page.evaluate("setProtoShell('browser'); renderPrototype()")

            print("2 · a phone runs a phone's browser")
            page.evaluate("setProtoDevice('mobile')")
            page.wait_for_timeout(200)
            check(page.locator(".proto-mobar").count() == 1
                  and page.locator(".proto-tabbar").count() == 0,
                  "mobile + Browser is a status bar and an address pill, not a desktop tab strip")
            page.evaluate("setProtoDevice('laptop')")
            page.wait_for_timeout(200)
            check(page.locator(".proto-tabbar .proto-dots i").count() == 3
                  and page.locator(".proto-urlbar-host").count() == 1,
                  "desk-sized keeps the window: traffic lights and a host-emphasised omnibox")

            # …and a tablet runs a tablet's browser. The golden declares ['desktop','mobile'], so
            # tablet is gated off here and the setter falls back to monitor — widen the list in the
            # page, assert the chrome, put it back. A tablet used to wear macOS traffic lights and
            # an extensions button inside an iPad bezel, and it was the one device whose OS status
            # bar vanished the moment you switched Chrome from App to Browser.
            F = "#proto-frame-wrap "
            page.evaluate("PB_REGISTRY.meta.devices = ['monitor','laptop','tablet','mobile'];"
                          " setProtoDevice('tablet'); setProtoShell('browser')")
            page.wait_for_timeout(300)
            check(page.evaluate("state.protoDevice") == "tablet", "the tablet size is reachable")
            check(page.locator(F + ".proto-statusbar").count() == 1
                  and page.locator(F + ".proto-tabbar").count() == 1,
                  "tablet + Browser keeps the OS status bar AND the tab strip")
            check(page.locator(F + ".proto-dots").count() == 0
                  and page.locator(F + ".proto-navbar .proto-navbtn--static").count() == 1,
                  "and drops what belongs to a desktop window: no traffic lights, no extensions")
            for sh in ("app", "none", "browser"):
                page.evaluate(f"setProtoShell('{sh}')")
                page.wait_for_timeout(200)
                check(page.locator(F + ".proto-statusbar").count() == 1,
                      f"  the tablet's status bar survives Chrome · {sh}")
                check(page.locator(F + ".proto-sb-island").count() == 0,
                      f"  and no phone island on a tablet ({sh})")
            page.evaluate("setProtoDevice('mobile')")
            page.wait_for_timeout(250)
            check(page.locator(F + ".proto-sb-island").count() == 1,
                  "the island is the phone's camera housing, and is still on the phone")
            page.evaluate("PB_REGISTRY.meta.devices = ['desktop','mobile'];"
                          " setProtoDevice('laptop'); setProtoShell('browser')")
            page.wait_for_timeout(250)

            print("3 · structure tree")
            menu()
            page.click(".proto-sandbox-menu .proto-menu-item:has-text('Structure tree')")
            page.wait_for_timeout(420)
            check(page.locator(".proto-sandbox-menu").count() == 0,
                  "toggling closes the menu that was covering the panel")
            check(page.eval_on_selector("#proto-struct-panel", "e => e.getBoundingClientRect().width") > 200,
                  "the panel is actually on screen")
            pages = page.locator(".pb-tree-page").all_inner_texts()
            check(len(pages) == 3, f"it lists the project's pages, by name and nothing else ({pages})")
            check(page.locator("#proto-struct-panel .pb-tree-node").count() == 0,
                  "no per-element description rows — page names only")
            fw = page.eval_on_selector("#proto-frame-wrap", "e => Math.round(e.getBoundingClientRect().width)")
            sw = page.eval_on_selector("#proto-stage", "e => e.clientWidth")
            check(0 < fw <= sw, f"and the preview shrinks beside it rather than being clipped ({fw} in {sw})")
            page.click("#proto-frame")
            page.wait_for_timeout(300)
            check(page.eval_on_selector("#proto-struct-panel", "e => e.classList.contains('is-open')"),
                  "a click in the prototype does NOT dismiss a panel the user opened")
            page.click(".proto-struct-close")
            page.wait_for_timeout(320)
            check(not page.eval_on_selector("#proto-struct-panel", "e => e.classList.contains('is-open')"),
                  "its own ✕ closes it")

            print("4 · compare — two devices, one scale, the real ratio")
            menu()
            check(page.locator(".proto-sandbox-menu select[aria-label='Compare with a second device']").count() == 0,
                  "Compare is a mode switch, not a device dropdown with an Off row")
            page.click(".proto-sandbox-menu .proto-menu-item:has-text('Compare')")
            page.wait_for_timeout(400)
            check(page.evaluate("state.protoDeviceB") is not None,
                  "switching it on picks a second device rather than arming an empty state")
            page.click(".proto-sandbox-menu [aria-label='Second device'] .proto-device-btn[aria-label*='Mobile']")
            page.wait_for_timeout(500)
            page.evaluate("document.querySelectorAll('.copy-popover,.copy-popover-backdrop')"
                          ".forEach(e => e.remove())")
            check(page.locator(".proto-frame-slot").count() == 2, "two frames")
            wa = page.eval_on_selector("#proto-frame-wrap", "e => e.offsetWidth")
            wb = page.eval_on_selector("#proto-frame-wrap-b", "e => e.offsetWidth")
            check((wa, wb) == (1280, 429), f"each lays out at its true CSS width ({wa}, {wb})")
            check(page.evaluate("getComputedStyle(document.getElementById('proto-frame-wrap')).transform") == "none"
                  and page.evaluate("getComputedStyle(document.getElementById('proto-pair')).transform") != "none",
                  "ONE transform, on the pair — never one fit per frame")
            ra = page.eval_on_selector("#proto-frame-wrap", "e => e.getBoundingClientRect().width")
            rb = page.eval_on_selector("#proto-frame-wrap-b", "e => e.getBoundingClientRect().width")
            check(abs((ra / rb) - (1280 / 429)) < 0.02,
                  f"so on screen the phone is still {1280/429:.2f}× narrower ({ra/rb:.2f})")
            sw, cw = page.eval_on_selector("#proto-stage", "e => [e.scrollWidth, e.clientWidth]")
            check(sw <= cw + 1, f"the pair is scaled to fit, not scrolled to ({sw} in {cw})")
            check(len(page.locator(".proto-frame-cap").all_inner_texts()) == 2,
                  "each frame says which device it is")
            # The stage narrows by 304px when the structure panel slides in. A single frame rides
            # that out in CSS; the pair's scale is JS, so it has to be recomputed or it runs under
            # the panel — which it did, until a ResizeObserver watched the stage.
            menu()
            page.click(".proto-sandbox-menu .proto-menu-item:has-text('Structure tree')")
            page.wait_for_timeout(900)
            sw2, cw2 = page.eval_on_selector("#proto-stage", "e => [e.scrollWidth, e.clientWidth]")
            check(sw2 <= cw2 + 1 and cw2 < cw,
                  f"and it refits when the structure panel takes the width ({sw2} in {cw2}, was {cw})")
            menu()
            page.click(".proto-sandbox-menu .proto-menu-item:has-text('Structure tree')")
            page.wait_for_timeout(500)
            page.evaluate("document.querySelectorAll('.copy-popover,.copy-popover-backdrop')"
                          ".forEach(e => e.remove())")

            print("5 · the second frame is a live frame, not a picture")
            page.eval_on_selector_all("#proto-frame-b .field__input", """els => els.forEach((e, i) => {
                e.value = i === 0 ? 'ada@example.com' : 'hunter2hunter2';
                e.dispatchEvent(new Event('input', { bubbles: true })); })""")
            page.click('#proto-frame-b [data-action="submit"]')
            page.wait_for_timeout(400)
            check(page.evaluate("state.protoScreenId") == "dashboard",
                  "submitting in frame B navigates — frame A's empty inputs do not veto it")
            check(page.locator(".proto-frame-slot").count() == 2, "and compare survives the navigation")
            menu()
            page.click(".proto-sandbox-menu .proto-device-btn[aria-label*='Mobile']")
            page.wait_for_timeout(400)
            check(page.evaluate("state.protoDeviceB") is None and page.locator(".proto-frame-slot").count() == 1,
                  "promoting the compared device to primary drops the compare — never a device beside itself")

            print("6 · scenario testing")
            page.evaluate("document.querySelectorAll('.copy-popover,.copy-popover-backdrop')"
                          ".forEach(e => e.remove())")
            scen = page.evaluate("pbTestScenarios()")
            check(len(scen) == 2 and all(s["text"] and s["text"] != "scenario" for s in scen),
                  f"every scenario carries its description ({[s['text'][:34] for s in scen]})")
            menu()
            labels = [t.strip().lower() for t in page.locator(".proto-sandbox-menu .sbx-row-lbl").all_inner_texts()]
            check("scenario testing" in labels and not any("terminal" in t for t in labels),
                  f"the row is Scenario testing ({labels})")
            opts = page.locator(".proto-sandbox-menu select[aria-label='Scenario testing'] option").all_inner_texts()
            check(any("Valid credentials land on the dashboard." in o for o in opts),
                  f"and the options read as the test cases do ({opts[1:]})")

            print("7 · Reset session is the last thing in the box")
            rows = page.eval_on_selector_all(
                ".proto-sandbox-menu > *",
                "els => els.map(e => [e.className || '', (e.textContent || '').trim()])")
            reset = [i for i, (c, t) in enumerate(rows) if "Reset session" in t]
            sbx = [i for i, (c, t) in enumerate(rows) if c.startswith("sbx-row")]
            check(reset and sbx and reset[0] > max(sbx),
                  f"reset sits after every control it resets (reset@{reset}, rows@{sbx})")

            print("8 · one active state for both segmented picks")
            menu()
            A = "el => { const c = getComputedStyle(el); return c.backgroundColor + '|' + c.color; }"
            sh = page.eval_on_selector(".proto-sandbox-menu .proto-shell-btn.active", A)
            dv = page.eval_on_selector(".proto-sandbox-menu .proto-toolbar .proto-device-btn.active", A)
            check(sh == dv, f"Chrome and Device look the same when selected\n        chrome={sh}\n        device={dv}")

            check(not errors, f"zero console errors throughout ({errors})")
            page.close()

        # 9 — in-page navigation has to reach BOTH frames. Needs a screen whose navigation stays
        # on the page, which the golden does not have.
        print("9 · compare mirrors what happens inside a screen")
        with tempfile.TemporaryDirectory() as tmp:
            with Server(make_wizard_registry(tmp)) as srv2:
                page = browser.new_page(viewport={"width": 1500, "height": 950})
                _offline(page)
                errs2 = []
                page.on("console", lambda m: errs2.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errs2.append(str(e)))
                page.goto(srv2.url, wait_until="domcontentloaded")
                page.wait_for_selector("#proto-frame", timeout=10000)
                page.evaluate("setProtoScreen('wizard'); setProtoCompare('mobile')")
                page.wait_for_timeout(600)
                A, B = "#proto-frame", "#proto-frame-b"
                step = lambda f: page.eval_on_selector(f + " [data-machine]", "e => e.getAttribute('data-step')")
                panes = lambda f: page.eval_on_selector_all(f + " [data-step-pane]",
                                                            "els => els.map(e => [e.dataset.stepPane, e.hidden])")
                check(page.locator(".proto-frame-slot").count() == 2, "two frames on the wizard screen")

                page.click(A + ' [data-step-go="two"]')
                page.wait_for_timeout(250)
                check(step(A) == step(B) == "two", f"a wizard step reaches both (A={step(A)} B={step(B)})")
                check(panes(A) == panes(B), f"and so does which pane is showing ({panes(B)})")

                page.click(A + ' [data-action="toggle-password"]')
                page.wait_for_timeout(200)
                ta = page.eval_on_selector(A + " input[type]", "e => e.type")
                tb = page.eval_on_selector(B + " input[type]", "e => e.type")
                check(ta == tb == "text", f"a revealed password reaches both (A={ta} B={tb})")

                page.fill(A + " #flt", "hello")
                page.wait_for_timeout(200)
                vb = page.eval_on_selector(B + " #flt", "e => e.value")
                check(vb == "hello", f"typed text reaches both — a DOM property, not markup (B={vb!r})")

                page.click(A + ' [data-action="submit"]')
                page.wait_for_timeout(300)
                ea, eb = page.locator(A + " .field__error").count(), page.locator(B + " .field__error").count()
                check(ea == eb == 1, f"an injected validation error reaches both (A={ea} B={eb})")

                # …and back the other way, without stealing the caret out of the frame being used.
                page.click(B + ' [data-step-go="one"]')
                page.wait_for_timeout(250)
                check(step(A) == step(B) == "one", f"and it mirrors from B to A too (A={step(A)})")
                page.fill(B + " #flt", "typed in B")
                page.wait_for_timeout(200)
                check(page.eval_on_selector(A + " #flt", "e => e.value") == "typed in B",
                      "typing in the second frame reaches the first")
                check(page.evaluate("document.activeElement.closest('.proto-screen').id") == "proto-frame-b",
                      "and the caret stays in the frame you are typing in")

                # 10 — navigation that never changes the screen. Scrolling to a section and a
                # handler that mixes `closest` with `getElementById` both used to land on one
                # frame only: the click worked, the content arrived, and the device you were
                # looking at did not move.
                print("10 · in-page navigation reaches both devices")
                page.evaluate("setProtoScreen('nav')")
                page.wait_for_timeout(400)
                sees = lambda f, sel: page.eval_on_selector(
                    f, "(fr, s) => { const t = fr.querySelector(s).getBoundingClientRect(),"
                       " v = fr.getBoundingClientRect();"
                       " return t.bottom > v.top + 4 && t.top < v.bottom - 4; }", sel)
                tab = lambda f: page.eval_on_selector_all(f + " [data-tab].active",
                                                          "e => e.map(x => x.dataset.tab)")
                pane = lambda f: page.eval_on_selector(f + " #pane", "e => e.textContent")

                page.click(A + " #btns")                       # scrollIntoView, driven from frame A
                page.wait_for_timeout(500)
                check(sees(A, "#sec3") and sees(B, "#sec3"),
                      f"a scroll to a section moves BOTH frames (A={sees(A, '#sec3')} B={sees(B, '#sec3')})")
                page.evaluate("document.querySelectorAll('.proto-screen').forEach(e => e.scrollTop = 0)")
                page.wait_for_timeout(300)
                page.click(B + " #jump")                       # an href="#id" anchor, from frame B
                page.wait_for_timeout(500)
                check(sees(A, "#sec3") and sees(B, "#sec3"),
                      f"and so does an anchor clicked in the second frame (A={sees(A, '#sec3')} B={sees(B, '#sec3')})")

                page.click(B + ' [data-tab="b"]')
                page.wait_for_timeout(300)
                check(tab(A) == tab(B) == ["b"] and pane(A) == pane(B) == "PANE B",
                      f"a handler that reads both `closest` and an id still lands whole — "
                      f"tabs {tab(A)}/{tab(B)}, panes {pane(A)!r}/{pane(B)!r}")
                page.click(A + ' [data-tab="a"]')
                page.wait_for_timeout(300)
                check(tab(A) == tab(B) == ["a"] and pane(A) == pane(B) == "PANE A",
                      f"and from the primary frame too ({tab(B)}, {pane(B)!r})")

                # A CSS-only view switch — `:has(#view:checked)`, how a prototype gets tabs and
                # master-detail without a line of JS. Radio groups are document-wide, so two
                # frames of one screen is two of every radio in it: the second frame's silently
                # unchecked the first frame's, whose view then computed to display:none. The
                # frame was not empty, it was showing a view that had lost its radio.
                shown = lambda f: page.eval_on_selector_all(
                    f + " .vw", "els => els.filter(e => getComputedStyle(e).display !== 'none')"
                               ".map(e => e.textContent)")
                check(shown(A) == shown(B) == ["VIEW ONE"],
                      f"a CSS-only radio view renders in BOTH frames (A={shown(A)} B={shown(B)})")
                page.eval_on_selector(B + " label[for='v2']", "e => e.click()")
                page.wait_for_timeout(300)
                check(shown(A) == shown(B) == ["VIEW TWO"],
                      f"and switching it in the second frame switches both (A={shown(A)} B={shown(B)})")
                page.eval_on_selector(A + " label[for='v1']", "e => e.click()")
                page.wait_for_timeout(300)
                check(shown(A) == shown(B) == ["VIEW ONE"],
                      f"and back, from the first (A={shown(A)} B={shown(B)})")

                check(not errs2, f"zero console errors while mirroring ({errs2})")
                page.close()

        browser.close()

    print()
    if _failures:
        print(f"✗ {len(_failures)} sandbox assertion(s) failed.")
        sys.exit(1)
    print("✓ All sandbox-shell assertions passed.")


if __name__ == "__main__":
    run()
