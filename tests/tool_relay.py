#!/usr/bin/env python3
"""
tool_relay.py — Playwright test for the Pick / Spacing relay between a shell and an embedded shell.

A page that frames a pb preview (?embed=1) cannot reach into the frame, so the shell carries the
bar's Pick and Spacing through postMessage (v1): the parent sends { source:'pb', type:'pb:tool',
tool, on }, the child answers { source:'pb-embed', type:'pb:tool-state' | 'pb:ready' }.

Boots the golden through serve.py, makes the preview page the PARENT, and frames the same server
twice: once with embed=1 (the child) and once without (a bystander that must be told nothing).
Asserts: parent Pick / Spacing reach the child; Esc, or a set call, inside the child un-presses the
parent's button; a reloaded child is told again for every tool that is on (pb:ready); the child
ignores a message from any window that is not its parent, and the parent one from any window that is
not an embed=1 iframe; an iframe without embed=1 receives nothing; an unknown tool is answered
supported:false once and ignored; the per-tool toast shows once, in the parent, per change.

Usage:  python3 tests/tool_relay.py
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


def _offline(page):
    """Serve nothing from outside the local preview (see test_inspect._offline for why)."""
    CT = {"script": "application/javascript", "stylesheet": "text/css",
          "font": "font/woff2", "image": "image/png"}

    def _handle(route):
        url = route.request.url
        if "127.0.0.1" in url or "localhost" in url:
            return route.continue_()
        return route.fulfill(status=200, body="",
                             content_type=CT.get(route.request.resource_type, "text/plain"))

    page.route("**/*", _handle)


def settle(page, ms=250):
    page.wait_for_timeout(ms)


def run():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed — skipping (dev/CI-only dependency).")
        print("  pip install playwright && playwright install chromium")
        sys.exit(2)

    print("Pick / Spacing relay through an embedded shell:")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            print(f"Could not launch Chromium ({e}). Run: playwright install chromium")
            sys.exit(2)
        with Server(GOLDEN) as srv:
            page = browser.new_page(viewport={"width": 1366, "height": 820})
            _offline(page)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(srv.url, wait_until="domcontentloaded")
            page.wait_for_selector(".meta-tab", timeout=10000)
            page.click(".meta-tab >> nth=0")  # Prototype: Pick and Spacing only exist there
            settle(page, 200)

            # The parent records what the frames send it and how often it toasts.
            page.evaluate("""() => {
                window.__in = []; window.__toasts = [];
                addEventListener('message', e => { if (e.data && e.data.source === 'pb-embed') window.__in.push(e.data); });
                const o = pbUiToast; pbUiToast = function (a, b) { window.__toasts.push(a); return o(a, b); };
            }""")
            # child = embed=1 ; bystander = the same shell without embed=1
            page.evaluate("""([a, b]) => {
                for (const [id, src] of [['child', a], ['bystander', b]]) {
                    const f = document.createElement('iframe'); f.id = id; f.src = src; f.style.cssText = 'width:600px;height:400px';
                    document.body.appendChild(f);
                }
            }""", [srv.url + "?embed=1&screen=login", srv.url + "?screen=login"])

            def frame(embed):
                for f in page.frames:
                    if f != page.main_frame and ("embed=1" in f.url) == embed:
                        return f
                return None

            def child_ready(f):
                f.wait_for_function("() => typeof pbPickSet === 'function' && document.body.classList.contains('pb-embed')"
                                    " && state.metaView === 'prototype'", timeout=15000)

            deadline = time.time() + 15
            while time.time() < deadline and not (frame(True) and frame(False)):
                page.wait_for_timeout(100)
            child, bystander = frame(True), frame(False)
            check(child is not None and bystander is not None, "both iframes loaded (embed=1 and a bystander)")
            child_ready(child)
            bystander.wait_for_function("() => typeof pbPickSet === 'function'", timeout=15000)
            bystander.evaluate("() => { window.__got = []; addEventListener('message', e => window.__got.push(e.data)); }")
            check(page.evaluate("() => (window.__in || []).some(m => m.type === 'pb:ready')"),
                  "the child announced pb:ready to its parent once it loaded")

            def on(f, name):
                return f.evaluate("n => window[n]", name)

            def wait_on(f, name, want, timeout=4000):
                try:
                    f.wait_for_function("([n, w]) => !!window[n] === w", arg=[name, want], timeout=timeout)
                    return True
                except Exception:
                    return False

            # 1. parent -> child
            page.evaluate("() => { window.__toasts.length = 0; pbPickSet(true); }")
            check(wait_on(child, "pbPickOn", True), "parent pbPickSet(true) turns the child's Pick on")
            settle(page)
            check(page.evaluate("() => window.__toasts") == ["Pick on"],
                  f"the parent toasts 'Pick on' once, not again for the child's reply (got {page.evaluate('() => window.__toasts')})")
            page.evaluate("() => pbSpacingSet(true)")
            check(wait_on(child, "pbSpacingOn", True), "parent pbSpacingSet(true) turns the child's Spacing on")
            check(child.evaluate("() => document.body.classList.contains('pb-picking') && document.body.classList.contains('pb-spacing')"),
                  "the child's body carries pb-picking and pb-spacing")

            # an iframe without embed=1 is told nothing
            settle(page)
            check(bystander.evaluate("() => window.__got.length") == 0 and not on(bystander, "pbPickOn") and not on(bystander, "pbSpacingOn"),
                  f"an iframe without embed=1 received nothing (got {bystander.evaluate('() => window.__got')})")

            # 2. child -> parent: a real Esc inside the frame (Pick first, then Spacing), I and M too
            page.evaluate("() => { window.__toasts.length = 0; }")
            child.evaluate("() => window.focus()")
            page.keyboard.press("Escape")
            check(wait_on(child, "pbPickOn", False), "Esc inside the frame ends the child's Pick")
            check(wait_on(page, "pbPickOn", False), "...and the parent's Pick with it")
            settle(page)
            check(page.locator(".meta-pick").get_attribute("aria-pressed") == "false", "the parent's Pick button is un-pressed")
            check(page.evaluate("() => window.__toasts") == ["Pick off"],
                  f"the parent toasts 'Pick off' once for a change that began in the child (got {page.evaluate('() => window.__toasts')})")
            check(page.evaluate("() => pbSpacingOn") is True and on(child, "pbSpacingOn"), "Spacing is untouched by Pick's Esc")
            page.keyboard.press("m")
            settle(page)
            check(page.evaluate("() => pbSpacingOn") is False and page.locator(".meta-spacing").get_attribute("aria-pressed") == "false",
                  "M inside the frame un-presses the parent's Spacing")
            page.keyboard.press("i")
            settle(page)
            check(page.evaluate("() => pbPickOn") is True and on(child, "pbPickOn"), "I inside the frame turns Pick on in both")
            child.evaluate("() => pbPickSet(false)")
            settle(page)
            check(page.evaluate("() => pbPickOn") is False, "the child's own pbPickSet(false) turns the parent's off")
            check(bystander.evaluate("() => window.__got.length") == 0, "the bystander still received nothing")

            # 3. a reloaded child (pb:ready) is told again for every tool that is on
            page.evaluate("() => { pbPickSet(true); pbSpacingSet(true); }")
            wait_on(child, "pbPickOn", True)

            def reload_child():
                # wait for the NEW document's pb:ready: a wait on the child alone can still see the old page
                page.evaluate("() => { window.__in.length = 0; document.getElementById('child').contentWindow.location.reload(); }")
                page.wait_for_function("() => window.__in.some(m => m.type === 'pb:ready')", timeout=15000)

            reload_child()
            check(wait_on(child, "pbPickOn", True) and wait_on(child, "pbSpacingOn", True),
                  "a reloaded child gets Pick and Spacing re-applied after its pb:ready")
            check(page.evaluate("() => window.__in.filter(m => m.type === 'pb:ready').length") == 1,
                  f"the reloaded child sent pb:ready once (got {page.evaluate('() => window.__in')})")
            page.evaluate("() => { pbPickSet(false); pbSpacingSet(false); }")
            check(wait_on(child, "pbPickOn", False) and wait_on(child, "pbSpacingOn", False), "parent off turns both off in the child")
            page.evaluate("() => { pbPickSet(true); }")
            wait_on(child, "pbPickOn", True)
            page.evaluate("() => { pbPickSet(false); }")
            reload_child()
            settle(page)
            check(not on(child, "pbPickOn"), "a reloaded child is not given a tool that is off")

            # 4. who may talk to whom
            #    (a) the child ignores a message from a window that is not its parent: the bystander is a sibling
            sent = bystander.evaluate("""() => { try { window.parent.frames[0].postMessage({ source: 'pb', v: 1, type: 'pb:tool', tool: 'pick', on: true }, '*'); return true; } catch (e) { return String(e); } }""")
            settle(page, 300)
            check(sent is True and not on(child, "pbPickOn"), f"a pb:tool from a sibling window is ignored by the child (sent={sent})")
            #    (b) wrong source / version / shape from the right window
            page.evaluate("""() => { const w = document.getElementById('child').contentWindow;
                w.postMessage({ source: 'nwb', v: 1, type: 'pb:tool', tool: 'pick', on: true }, '*');
                w.postMessage({ source: 'pb', v: 2, type: 'pb:tool', tool: 'pick', on: true }, '*');
                w.postMessage({ source: 'pb', v: 1, type: 'pe:pick', tool: 'pick', on: true }, '*');
                w.postMessage({ source: 'pb', v: 1, type: 'pb:tool', tool: 'pick', on: 'yes' }, '*');
                w.postMessage('pb:tool', '*'); w.postMessage(null, '*'); w.postMessage([1, 2], '*'); }""")
            settle(page, 300)
            check(not on(child, "pbPickOn"), "a message with the wrong source, version, type, value or shape does nothing")
            #    (c) the parent ignores a pb-embed message from a window that is not one of its embed=1 iframes
            bystander.evaluate("() => window.parent.postMessage({ source: 'pb-embed', v: 1, type: 'pb:tool-state', tool: 'pick', on: true }, '*')")
            settle(page, 300)
            check(page.evaluate("() => pbPickOn") is False, "a pb:tool-state from an iframe without embed=1 is ignored by the parent")
            #    (d) an unknown tool: answered supported:false once, never acted on
            page.evaluate("() => { window.__in.length = 0; const w = document.getElementById('child').contentWindow;"
                          " w.postMessage({ source: 'pb', v: 1, type: 'pb:tool', tool: 'zoom', on: true }, '*');"
                          " w.postMessage({ source: 'pb', v: 1, type: 'pb:tool', tool: 'zoom', on: true }, '*'); }")
            settle(page, 300)
            zoom = page.evaluate("() => window.__in.filter(m => m.tool === 'zoom')")
            check(len(zoom) == 1 and zoom[0].get("supported") is False and zoom[0].get("on") is False,
                  f"an unknown tool is answered supported:false once (got {zoom})")
            check(page.evaluate("() => pbPickOn") is False and not on(child, "pbPickOn"), "...and the parent ignores that reply")
            #    (e) a parent that is not a shell with the relay target: the child never relays to its own frames without embed=1
            check(child.evaluate("() => document.querySelectorAll('iframe').length") == 0, "the child frames nothing, so it relays to no one")

            check(errors == [], f"no page errors in the parent or the frames (got {errors[:3]})")
            page.close()
        browser.close()

    print()
    if _failures:
        print(f"✗ {len(_failures)} relay assertion(s) failed.")
        sys.exit(1)
    print("✓ All relay assertions passed.")


if __name__ == "__main__":
    run()
