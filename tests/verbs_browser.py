#!/usr/bin/env python3
"""
verbs_browser.py — the two D-28 runtime verbs, driven in a REAL browser.

The verbs shipped with unit coverage (tests/logic_contract.py §6: they exist once in
runtime.js, reach the rendered page, and are wired in both shells) and with a jsdom drive
(tests/e2e_smoke.py T2.3). Neither can answer the questions that decide whether the verbs
actually work for a person:

  · jsdom has no cascade worth the name, so "[data-step-pane][hidden] at a strength a
    project's CSS cannot beat" was a claim about a stylesheet nobody had ever resolved.
  · jsdom has no focus model and no selection, so "what survives a re-render" was only ever
    checked for `value` — never for the caret sitting in it.
  · jsdom has no IME. The project this was built for is Vietnamese, and D-28's own rationale
    names IME composition as the thing a naive focus-restore destroys.

So this file asserts the parts only a browser can settle, and it is deliberately explicit
about the boundary of what data-preserve promises: it restores DECLARED STATE, not the
caret. Where that boundary bites, the check records it rather than asserting it away.

Dev/CI-only dependency (NS4 — never shipped to users, never pip-installed by the plugin):
  python3 -m venv .venv && .venv/bin/pip install playwright && .venv/bin/playwright install chromium
Usage:  .venv/bin/python tests/verbs_browser.py
Exit:   0 = all passed · 1 = a failure · 2 = Playwright/browser not available
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVE = os.path.join(ROOT, "pb", "tools", "serve.py")

_failures = []
_notes = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        _failures.append(msg)


def note(msg):
    print("  · " + msg)
    _notes.append(msg)


# ───────────────────────── the fixture ─────────────────────────────────────────
# One screen carrying both verbs, plus a project stylesheet that TRIES to force every
# wizard pane visible — that rule is the whole point of the cascade check below.

BODY = r"""
function pbVbInner() {
  window.PB_VB_GEN = (window.PB_VB_GEN || 0);
  return '<input id="flt" data-preserve value="" placeholder="Filter">'
    + '<input id="chk" type="checkbox" data-preserve>'
    + '<select id="sel" data-preserve><option value="a">A</option><option value="b">B</option></select>'
    + '<span id="gen">' + window.PB_VB_GEN + '</span>';
}

/* Records, from inside each control's own change handler, what EVERY control read at that
   moment. "Restore everything first, notify second" is only observable this way: if the
   runtime fired as it went, the first handler would see its siblings still holding the
   rebuilt (empty) values. */
function pbVbWatch() {
  window.PB_VB_LOG = [];
  ['input', 'change'].forEach(function (name) {
    document.getElementById('host').addEventListener(name, function (e) {
      window.PB_VB_LOG.push({
        type: name,
        id: e.target.id,
        sawFlt: (document.getElementById('flt') || {}).value,
        sawChk: !!(document.getElementById('chk') || {}).checked,
        sawSel: (document.getElementById('sel') || {}).value
      });
    });
  });
}

function pbVbRerender() {
  window.PB_VB_GEN = (window.PB_VB_GEN || 0) + 1;
  var host = document.getElementById('host');
  return pbPreserve(function () { host.innerHTML = pbVbInner(); }, host);
}

function renderScrVerbs(props) {
  return '<style>[data-step-pane]{display:block !important;}</style>'
    + '<div id="host">' + pbVbInner() + '</div>'
    + '<button id="rr" onclick="pbVbRerender()">Rerender</button>'
    + '<div id="wiz" data-machine="wiz" data-step-initial="one">'
    +   '<section data-step-pane="one">PANE ONE<button id="go2" data-step-go="two">Next</button></section>'
    +   '<section data-step-pane="two">PANE TWO<button id="go3" data-step-go="three">Next</button></section>'
    +   '<section data-step-pane="three">PANE THREE</section>'
    +   '<i data-step-dot="one"></i><i data-step-dot="two"></i><i data-step-dot="three"></i>'
    + '</div>';
}
"""


def fixture(d):
    os.makedirs(os.path.join(d, "render", "screens"), exist_ok=True)
    with open(os.path.join(d, "render/screens/verbs.js"), "w", encoding="utf-8") as f:
        f.write(BODY)
    reg = {
        "meta": {"name": "verbs", "schemaVersion": 11, "shell": "none"},
        "tokens": {}, "components": [],
        "screens": [{"id": "verbs", "name": "Verbs", "level": "page",
                     "renderFn": "renderScrVerbs", "renderSrc": "render/screens/verbs.js"}],
        "flow": {"populated": False}, "erd": {"populated": False},
        "ia": {"populated": False}, "runtime": [],
    }
    path = os.path.join(d, "registry.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


class Server:
    """Boot serve.py on a registry; parse the chosen URL from its stdout. (e2e_smoke pattern.)"""

    def __init__(self, registry):
        self.registry, self.proc, self.url = registry, None, None

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
        print("Playwright not installed — skipping the browser verb drive (dev/CI-only).")
        print("  python3 -m venv .venv && .venv/bin/pip install playwright")
        print("  .venv/bin/playwright install chromium")
        sys.exit(2)

    tmp = tempfile.mkdtemp(prefix="pb-verbs-browser-")
    registry = fixture(tmp)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            print(f"Could not launch Chromium ({e}). Run: .venv/bin/playwright install chromium")
            sys.exit(2)
        page = browser.new_page()
        _offline(page)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        with Server(registry) as srv:
            # domcontentloaded, not networkidle: serve.py holds an SSE reload stream open, so
            # the network is never idle and the wait would always time out.
            page.goto(srv.url, wait_until="domcontentloaded")
            page.wait_for_selector("#flt", timeout=10000)

            # ── 1 · data-step: the cascade, which is the whole reason this file is a browser test
            print("1 · data-machine / data-step in a real cascade")
            check(page.is_visible("[data-step-pane='one']"), "the initial pane is visible")
            check(not page.is_visible("[data-step-pane='two']"),
                  "a non-current pane is NOT visible, though the project's own CSS says "
                  "[data-step-pane]{display:block !important}")
            check(page.eval_on_selector("[data-step-pane='two']", "el => el.hidden") is True,
                  "because the runtime sets .hidden, and the shell's [hidden] rule outranks it")
            check(page.get_attribute("[data-step-dot='one']", "data-current") == "true",
                  "the step dot tracks the current state")

            page.click("#go2")
            check(page.is_visible("[data-step-pane='two']") and not page.is_visible("[data-step-pane='one']"),
                  "data-step-go advances the machine on a real click")
            check(page.get_attribute("[data-step-dot='two']", "data-current") == "true",
                  "and the dots follow")
            page.evaluate("pbSetStep('wiz','three')")
            check(page.is_visible("[data-step-pane='three']"),
                  "pbSetStep drives a transition a click cannot express")

            # ── 2 · data-preserve: declared state across a real re-render
            print("2 · data-preserve across a re-render that destroys the controls")
            page.evaluate("pbVbWatch()")
            page.fill("#flt", "kết quả")          # non-ASCII on purpose
            page.check("#chk")
            page.select_option("#sel", "b")
            gen_before = page.text_content("#gen")
            # Clear the log AFTER the setup typing: page.fill/check/select_option each fire real
            # input+change of their own, and counting those as restores would make the assertion
            # below pass for the wrong reason.
            page.evaluate("window.PB_VB_LOG = []")
            restored = page.evaluate("pbVbRerender()")
            check(page.text_content("#gen") != gen_before,
                  "the re-render really replaced the markup (generation counter moved)")
            check(page.input_value("#flt") == "kết quả", "a non-ASCII value survives")
            check(page.is_checked("#chk"), "a checkbox survives")
            check(page.input_value("#sel") == "b", "a select survives")
            check(restored == 3, f"pbPreserve reports 3 restored controls (got {restored})")

            log = page.evaluate("window.PB_VB_LOG")
            kinds = [(e["type"], e["id"]) for e in log]
            check(sorted(kinds) == sorted([(t, i) for i in ("flt", "chk", "sel")
                                           for t in ("input", "change")]),
                  "each restored control fires input + change exactly once")
            first = log[0] if log else {}
            check(bool(log) and first.get("sawFlt") == "kết quả" and first.get("sawChk") is True
                  and first.get("sawSel") == "b",
                  "the FIRST handler already sees every sibling restored — "
                  "restore-all-then-notify, not notify-as-you-go")

            # ── 3 · the caret: what data-preserve does NOT claim, verified rather than assumed
            print("3 · focus and caret — the documented boundary")
            page.click("#flt")
            page.evaluate("document.getElementById('flt').setSelectionRange(3,3)")
            focused_before = page.evaluate("document.activeElement && document.activeElement.id")
            page.evaluate("pbVbRerender()")
            focused_after = page.evaluate("document.activeElement && document.activeElement.id")
            check(focused_before == "flt", "the field is focused before the re-render")
            if focused_after == "flt":
                check(True, "focus survives the re-render")
                caret = page.evaluate("document.getElementById('flt').selectionStart")
                check(caret == 3, f"and the caret holds its offset (got {caret})")
            else:
                note("focus does NOT survive: data-preserve restores declared state "
                     "(value/checked/scroll/open/active), never the caret. A surface that "
                     "re-renders under the user's fingers must render its input ONCE and "
                     "repaint only the hosts around it — the D-26 Data-tab rule. This is a "
                     "boundary, not a regression; the check records it so a future change "
                     "that silently adds focus-restore has to come past this line.")
                check(page.input_value("#flt") == "kết quả",
                      "the value is still intact, which is what the verb does promise")

            # ── 4 · IME composition, the case D-28's rationale names
            print("4 · IME composition (the Vietnamese case)")
            page.click("#flt")
            page.evaluate("document.getElementById('flt').value = ''")
            cdp = page.context.new_cdp_session(page)
            cdp.send("Input.imeSetComposition",
                     {"text": "ket", "selectionStart": 3, "selectionEnd": 3})
            mid = page.input_value("#flt")
            cdp.send("Input.insertText", {"text": "kết"})
            done = page.input_value("#flt")
            check(mid == "ket", f"a composition is in flight in the field (got {mid!r})")
            check(done == "kết", f"and commits to the composed form (got {done!r})")
            page.evaluate("pbVbRerender()")
            check(page.input_value("#flt") == "kết",
                  "a committed composition survives a re-render unmangled")

            check(not errors, f"zero console / page errors throughout ({len(errors)} seen)")
            for e in errors[:5]:
                print("      " + e[:160])

        browser.close()

    print()
    if _failures:
        print("FAIL — %d regression(s)" % len(_failures))
        return 1
    print("PASS — the two runtime verbs, driven in Chromium"
          + (" (%d boundary note(s))" % len(_notes) if _notes else ""))
    return 0


if __name__ == "__main__":
    sys.exit(run())
