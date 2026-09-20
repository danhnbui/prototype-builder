#!/usr/bin/env python3
"""
e2e_smoke.py — the browser smoke test for the Product Builder shell.

Boots pb/tools/serve.py on the golden fixture and drives a real Chromium via
Playwright, asserting the behaviours the CPTO audit verified by hand:

  1. all 4 doc tabs render (Prototype · Project Summary · UX Design · Data — components live on the DS site)
  2. a registry design token reaches :root (Principle 1, runtime side)
  3. an empty submit shows >= 2 inline errors with the danger-token border
  4. a valid submit navigates to the next screen
  5. a view-only (/pb:handoff-close --people) artifact hides EVERY authoring CTA, on all 4 tabs
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

            # 1. four tabs (Prototype · Project Summary · UX Design · Data — components live on the DS site)
            check(page.locator(".meta-tab").count() == 4, "4 doc tabs render")

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

            # (The UI Design tab was removed — components now live on the design-system site;
            #  the apostrophe-named "User's Login Card" render is covered by tests/r5_ds_site.py.)

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
                check(page.locator(".meta-tab").count() == 4,
                      "page with a </script> body still boots (4 tabs render)")
                check(not errors, f"zero console errors on the page-killer fixture ({errors})")
                page.close()

        # ── T2.3 — the two schema-11 runtime verbs, driven for real ────────────
        # Structural tests can only prove the helpers are PRESENT. These two verbs exist to
        # replace per-project JS, so the thing that matters is that a project author gets the
        # behaviour without writing any: a wizard that shows one pane at a time, and a
        # re-render that does not throw away what the user had set underneath it.
        print("runtime verbs (data-machine / data-step, data-preserve):")
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "render", "screens"))
            os.makedirs(os.path.join(tmp, "runtime"))
            with open(os.path.join(tmp, "runtime", "store.js"), "w", encoding="utf-8") as f:
                f.write(
                    "var pbVerbRows = ['Alpha', 'Beta', 'Gamma', 'Delta'];\n"
                    # The real case: a save re-renders the WHOLE surface, destroying every
                    # control the user had set. The rows only follow the filter once the
                    # control's own handler runs again, against the restored value.
                    "function pbVerbRerender() {\n"
                    "  pbPreserve(function () {\n"
                    "    document.getElementById('verb-block').innerHTML = pbVerbBlock();\n"
                    "  });\n"
                    "}\n"
                    "function pbVerbBlock() {\n"
                    "  return '<input id=\"verb-q\" class=\"field__input\" data-preserve oninput=\"pbVerbApply()\">'\n"
                    "    + '<input type=\"checkbox\" id=\"verb-chk\" data-preserve>'\n"
                    "    + '<ul id=\"verb-list\">' + pbVerbRows_() + '</ul>';\n"
                    "}\n"
                    "function pbVerbApply() { document.getElementById('verb-list').innerHTML = pbVerbRows_(); }\n"
                    "function pbVerbRows_() {\n"
                    "  var el = document.getElementById('verb-q'), q = el ? (el.value || '') : '';\n"
                    "  return pbVerbRows.filter(function (r) { return r.toLowerCase().indexOf(q.toLowerCase()) >= 0; })\n"
                    "    .map(function (r) { return '<li>' + r + '</li>'; }).join('');\n"
                    "}\n")
            with open(os.path.join(tmp, "render", "screens", "home.js"), "w", encoding="utf-8") as f:
                f.write(
                    "function renderScrVerbs() {\n"
                    "  return '<div data-machine=\"wiz\" data-step-initial=\"one\">'\n"
                    "    + '<span data-step-dot=\"one\">1</span><span data-step-dot=\"two\">2</span>'\n"
                    "    + '<div data-step-pane=\"one\">one <button data-step-go=\"two\">Next</button></div>'\n"
                    "    + '<div data-step-pane=\"two\">two</div>'\n"
                    "  + '</div>'\n"
                    "  + '<div id=\"verb-block\">' + pbVerbBlock() + '</div>';\n"
                    "}\n")
            reg = {
                "meta": {"name": "Verbs", "schemaVersion": 11, "device": "laptop", "devices": ["laptop"]},
                "tokens": {}, "components": [],
                "runtime": [{"id": "store", "src": "runtime/store.js", "why": "the demo's filter state"}],
                "screens": [{"id": "home", "name": "Home", "level": "page",
                             "renderFn": "renderScrVerbs", "renderSrc": "render/screens/home.js"}],
                "flow": {"populated": False}, "erd": {"populated": False},
            }
            path = os.path.join(tmp, "registry.json")
            json.dump(reg, open(path, "w", encoding="utf-8"), indent=2)
            with Server(path) as srv:
                page = browser.new_page()
                errors = []
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(srv.url, wait_until="domcontentloaded")
                page.wait_for_selector('[data-machine="wiz"]', timeout=10000)

                check(page.evaluate("typeof window.pbVerbRows_ === 'function'"),
                      "a registry.runtime[] module is defined in the page scope")
                root = page.locator('[data-machine="wiz"]')
                check(root.get_attribute("data-step") == "one",
                      "the machine opens on data-step-initial, reflected on the root")
                check(page.locator('[data-step-pane="one"]').is_visible()
                      and not page.locator('[data-step-pane="two"]').is_visible(),
                      "only the current pane is visible")
                check(page.locator('[data-step-dot="one"]').get_attribute("data-current") == "true",
                      "the progress dots follow the state")
                page.click('[data-step-go="two"]')
                check(root.get_attribute("data-step") == "two"
                      and page.locator('[data-step-pane="two"]').is_visible()
                      and not page.locator('[data-step-pane="one"]').is_visible(),
                      "a data-step-go click advances it and the panes swap")
                page.evaluate("pbSetStep(document.querySelector('[data-machine]'), 'one')")
                check(page.locator('[data-step-pane="one"]').is_visible(),
                      "pbSetStep drives a transition a click cannot express")

                # 'al' matches Alpha only — Beta, Gamma and Delta have no 'al'.
                page.locator("#verb-q").fill("al")
                page.click("#verb-chk")
                check(page.locator("#verb-list li").count() == 1, "the user has filtered down to one row")
                page.evaluate("pbVerbRerender()")
                page.wait_for_timeout(100)
                check(page.evaluate("document.getElementById('verb-q').value") == "al",
                      "the text is back in the rebuilt control")
                check(page.evaluate("document.getElementById('verb-chk').checked") is True,
                      "so is the checkbox")
                check(page.locator("#verb-list li").count() == 1
                      and page.evaluate("document.querySelector('#verb-list li').textContent") == "Alpha",
                      "and the surface underneath is still filtered — the restore re-fired the handler")
                check(not errors, f"zero console errors on the verb fixture ({errors})")
                page.close()

        # ── view-only artifact hides every authoring CTA, on all 4 tabs ─────────
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
                for i in range(4):
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
