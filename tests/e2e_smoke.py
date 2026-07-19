#!/usr/bin/env python3
"""
e2e_smoke.py — the browser smoke test for the Product Builder shell.

Boots pb/tools/serve.py on the golden fixture and drives a real Chromium via
Playwright, asserting the behaviours the CPTO audit verified by hand:

  1. all 5 doc tabs render
  2. a registry design token reaches :root (Principle 1, runtime side)
  3. an empty submit shows >= 2 inline errors with the danger-token border
  4. a valid submit navigates to the next screen
  5. a view-only (/pb:handoff-close --people) artifact hides EVERY authoring CTA, on all 5 tabs
  6. zero console / page errors throughout

Dev/CI-only dependency (NS4 — never shipped to users, never pip-installed by the plugin):
  pip install playwright && playwright install chromium

Usage:  python3 tests/e2e_smoke.py
Exit:   0 = all passed · 1 = a failure · 2 = Playwright/browser not available
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVE = os.path.join(ROOT, "pb", "tools", "serve.py")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")
DANGER_RGB = "rgb(220, 38, 38)"  # #dc2626, the golden's danger token

_failures = []


def check(cond, msg):
    mark = "✓" if cond else "✗"
    print(f"  {mark} {msg}")
    if not cond:
        _failures.append(msg)


class Server:
    """Boot serve.py on a registry; parse the chosen URL from its stdout."""

    def __init__(self, registry):
        self.registry = registry
        self.proc = None
        self.url = None

    def __enter__(self):
        self.proc = subprocess.Popen(
            [sys.executable, SERVE, self.registry, "--no-open", "--host", "127.0.0.1"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
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


def make_viewonly_registry(tmpdir, unpopulate=False):
    """Copy the golden project (registry + render/ body files) and flip on config.viewOnly
    — the /pb:handoff-close --people shape. With unpopulate=True, also empty the flow/erd tabs
    so the artifact exercises empty-state tabs in view-only (T3.3)."""
    src_dir = os.path.dirname(GOLDEN)
    render_src = os.path.join(src_dir, "render")
    if os.path.isdir(render_src):
        shutil.copytree(render_src, os.path.join(tmpdir, "render"))
    reg = json.load(open(GOLDEN, encoding="utf-8"))
    reg.setdefault("config", {})["viewOnly"] = True
    if unpopulate:
        reg["flow"] = {"populated": False}
        reg["erd"] = {"populated": False}
    path = os.path.join(tmpdir, "registry.json")
    json.dump(reg, open(path, "w", encoding="utf-8"), indent=2)
    return path


def run():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed — skipping e2e (dev/CI-only dependency).")
        print("  pip install playwright && playwright install chromium")
        sys.exit(2)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            print(f"Could not launch Chromium ({e}). Run: playwright install chromium")
            sys.exit(2)

        # ── core behaviours on the golden ───────────────────────────────────────
        print("golden fixture:")
        with Server(GOLDEN) as srv:
            page = browser.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(srv.url, wait_until="domcontentloaded")
            page.wait_for_selector(".meta-tab", timeout=10000)

            # 1. five tabs
            check(page.locator(".meta-tab").count() == 5, "5 doc tabs render")

            # 1b. build_html fills {{PB_SHELL_VERSION}}; the version now lives in the Sandbox menu footer.
            page.click(".meta-sandbox")
            page.wait_for_timeout(120)
            ver = page.locator(".proto-sandbox-menu .sbx-foot").inner_text()
            check(re.match(r"pb v\d", ver) is not None,
                  f"Sandbox menu footer shows the shell version ({ver!r})")
            page.evaluate("typeof closeCopyPopover==='function' && closeCopyPopover()")
            page.wait_for_timeout(80)

            # 2. registry token reaches :root
            brand = page.evaluate(
                "getComputedStyle(document.documentElement).getPropertyValue('--brand').trim()")
            check(brand == "#4f46e5", f"registry token applied to :root (--brand={brand!r})")

            # 3. empty submit -> >=2 errors with the danger border
            page.click('.meta-tab >> nth=0')  # Prototype tab (default, but be explicit)
            page.click('#proto-frame [data-action="submit"]')
            page.wait_for_timeout(150)
            n_err = page.locator("#proto-frame .field__error:visible").count()
            check(n_err >= 2, f"empty submit shows >= 2 inline errors (got {n_err})")
            border = page.evaluate(
                "(() => { const i = document.querySelector('#proto-frame .field__input');"
                " return i ? getComputedStyle(i).borderColor : ''; })()")
            check(border == DANGER_RGB, f"error border uses the danger token ({border})")

            # 4. valid submit navigates
            inputs = page.locator("#proto-frame .field__input")
            inputs.nth(0).fill("ada@example.com")
            inputs.nth(1).fill("hunter2hunter2")
            page.click('#proto-frame [data-action="submit"]')
            page.wait_for_timeout(200)
            check("Welcome back" in page.locator("#proto-frame").inner_text(),
                  "valid submit navigates to the dashboard")

            # T1.4 — a component named with an apostrophe ("User's Login Card") must
            # render in the UI Design list and open its detail (pbEscape escapes quotes).
            page.click('.meta-tab >> nth=3')  # UI Design tab
            page.wait_for_timeout(150)
            row = page.locator(".uid-row", has_text="User's Login Card")
            check(row.count() >= 1, "apostrophe-named component renders in the UI Design list")
            if row.count():
                row.first.click()
                page.wait_for_timeout(150)
                check(page.locator(".uid-detail-title", has_text="User's Login Card").count() >= 1,
                      "apostrophe-named component opens its detail (stacked, no tabs)")

            check(not errors, f"zero console errors on golden ({errors})")
            page.close()

        # ── T2.2 — a body containing </script> must BOOT (the </ -> <\/ escape) ──
        print("page-killer fixture (</script> in a body):")
        with tempfile.TemporaryDirectory() as tmp:
            reg = {
                "meta": {"name": "Page Killer", "schemaVersion": 3, "device": "desktop"},
                "tokens": {"danger": {"value": "#dc2626", "kind": "color"}},
                "components": [], "screens": [{
                    "id": "home", "name": "Home", "renderFn": "renderScreenHome",
                    "layout": {"type": "stack", "gap": 16, "maxWidth": 720, "padding": 32},
                    "elements": [], "logicNotes": [],
                    "render": "return '<div>boots</div><b></script><i>still alive</i>';",
                }],
                "staleness": {}, "flow": {"populated": False}, "erd": {"populated": False},
            }
            path = os.path.join(tmp, "registry.json")
            json.dump(reg, open(path, "w", encoding="utf-8"), indent=2)
            with Server(path) as srv:
                page = browser.new_page()
                errors = []
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(srv.url, wait_until="domcontentloaded")
                page.wait_for_selector(".meta-tab", timeout=10000)
                check(page.locator(".meta-tab").count() == 5,
                      "page with a </script> body still boots (5 tabs render)")
                check(not errors, f"zero console errors on the page-killer fixture ({errors})")
                page.close()

        # ── view-only artifact hides every authoring CTA, on all 5 tabs ─────────
        print("view-only (--people) artifact:")
        with tempfile.TemporaryDirectory() as tmp:
            # unpopulate=True empties flow/erd so the UX Design + Data tabs render their
            # empty-state cards — the exact case where the authoring-CTA leak lived (T3.3).
            vpath = make_viewonly_registry(tmp, unpopulate=True)
            with Server(vpath) as srv:
                page = browser.new_page()
                errors = []
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(srv.url, wait_until="domcontentloaded")
                page.wait_for_selector(".meta-tab", timeout=10000)
                check(page.evaluate("document.body.classList.contains('view-only')"),
                      "body.view-only is set")
                cta_sel = ".sync-button, .fp-panel, .empty-state-cta, .empty-state-actions"
                for i in range(5):
                    page.click(f".meta-tab >> nth={i}")
                    page.wait_for_timeout(120)
                    visible = page.locator(f"{cta_sel} >> visible=true").count()
                    label = page.locator(".meta-tab").nth(i).inner_text().strip()
                    check(visible == 0, f"no authoring CTA visible on '{label}' tab ({visible})")
                check(not errors, f"zero console errors on view-only ({errors})")
                page.close()

        browser.close()

    print()
    if _failures:
        print(f"✗ {len(_failures)} e2e assertion(s) failed.")
        sys.exit(1)
    print("✓ All e2e smoke assertions passed.")


if __name__ == "__main__":
    run()
