#!/usr/bin/env python3
"""
test_inspect.py — Playwright test for the Prototype ⌥-hover inspect feature.

Boots the golden through serve.py and verifies: ⌥-hover shows the inspect label with the
element's structured id path; ⌥-click copies (toast) WITHOUT navigating; a normal click still
navigates (zero regression); a non-tagged element still yields a screen-scoped fallback path.

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
            check(page.locator('.proto-toast', has_text="Copied").count() >= 1,
                  "⌥-click shows a 'Copied' toast")

            # A normal (no-Alt) valid submit STILL navigates — zero runtime regression.
            inp = page.locator('#proto-frame .field__input')
            inp.nth(0).fill("ada@example.com")
            inp.nth(1).fill("hunter2hunter2")
            page.click('#proto-frame [data-action="submit"]')
            page.wait_for_timeout(220)
            check(page.evaluate("() => state.protoScreenId") == "dashboard",
                  "a normal submit still navigates (no inspect regression)")

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

            page.close()
        browser.close()

    print()
    if _failures:
        print(f"✗ {len(_failures)} inspect assertion(s) failed.")
        sys.exit(1)
    print("✓ All inspect assertions passed.")


if __name__ == "__main__":
    run()
