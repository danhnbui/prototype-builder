#!/usr/bin/env python3
"""
tc_shapes.py — the Test Cases list reads both shapes of a scenario (round 3).

A scenario is either {text, test:{steps[], expect[]}, lastResult:{status}} (written by /pb:plan --flow,
recorded by /pb:test) or {id, test:"the label", steps:"…", expect:"…", lastResult:{result, note}} (written
by hand, recorded by a headless run — one real project's 204). The list used to show the second shape
with an empty label and every case as "Not run". This pins, in Chromium:

  * the label is `text`, else `test` when that is a string, else `title`
  * the verdict is `lastResult.status || lastResult.result`, with its own glyph and words for
    pass · fail · blocked · retired · untested by design · not run
  * the tally above the list counts them (and a `result`-shaped pass is not "stale")
  * a row opens into its steps and what it expects, as written; several rows can be open at once
  * a case with no `test` and no result stays a manual ☐

Usage:  python3 tests/tc_shapes.py
Exit:   0 = pass (the browser half is skipped, and says so, without Playwright) · 1 = a failure
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))

import render  # noqa: E402

SHELL = os.path.join(ROOT, "pb", "template", "prototype.html")
FAIL = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


STORIES = [
    {"title": "US-1 Pick a ward", "scenarios": [
        # the hand-written shape: `test` is the label, steps/expect are strings, the verdict is `result`
        {"id": "S1.1", "test": "Ward picker offers only wards that have geometry", "steps": "Open workspace; open the ward picker",
         "expect": "Every option resolves to a loaded tile ward", "category": "functional", "lastResult": {"result": "pass", "at": "headless"}},
        {"id": "S1.2", "test": "The dropped master is counted, not hidden", "steps": "Read the note", "expect": "11.043 wards are reported",
         "lastResult": {"result": "retired", "at": "headless", "note": "the disclosure lived in the sidebar, which is replaced"}},
        {"id": "S1.3", "test": "A layer toggle re-renders under 100ms", "steps": "Toggle a layer", "expect": "Under 100ms",
         "lastResult": {"result": "untested-by-design", "at": "headless", "note": "no timing in a prototype"}},
        {"id": "S1.4", "test": "Hub options read code-first", "steps": "Open the hub list", "expect": "Codes lead"},
        {"id": "S1.5", "test": "A save that fails says so", "steps": "Save offline", "expect": "A toast", "lastResult": {"result": "fail"}},
        {"id": "S1.6", "test": "A save behind a login", "steps": "Sign in", "expect": "A toast", "lastResult": {"result": "blocked"}},
    ]},
    {"title": "US-2 Review", "scenarios": [
        # the planned shape: `text` is the label, `test` is a block, the verdict is `status`
        {"text": "Submitting an empty form shows a border AND a message. A second sentence follows.", "category": "ux",
         "test": {"start": "login", "steps": [{"do": "click", "target": "submit"}], "expect": [{"text": "Required"}]},
         "lastResult": {"status": "pass", "inputs": {}}},     # inputs recorded, none moved: current
        {"title": "Titled only", "test": {"start": "login", "steps": [], "expect": []}},
        "A bare string: checked by hand",
    ]},
]


def build(project):
    reg = {"meta": {"schemaVersion": 12, "name": "TC shapes"},
           "screens": [{"id": "home", "name": "Home", "renderSrc": "render/screens/home.js", "renderFn": "renderScreenHome"}],
           "components": [], "ia": {"populated": True, "rules": []},
           "flow": {"populated": True, "mermaid": "flowchart LR\n  a[Start] --> b[End]", "flows": [], "stories": STORIES}}
    os.makedirs(os.path.join(project, "render", "screens"))
    with open(os.path.join(project, "registry.json"), "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False)
    with open(os.path.join(project, "render", "screens", "home.js"), "w", encoding="utf-8") as f:
        f.write("return '<main>home</main>';\n")


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ○ Playwright not installed — the browser half is skipped (pip install playwright)")
        return
    print("the Test Cases list, in Chromium")
    tmp = tempfile.mkdtemp()
    try:
        project = os.path.join(tmp, "tc")
        build(project)
        out = os.path.join(project, "prototype.html")
        render.render_file(os.path.join(project, "registry.json"), SHELL, out)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            # offline: the web font and the mermaid CDN are not under test, and a slow network must not fail it
            page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("file:", "data:", "blob:")) else r.abort())
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto("file://" + out)
            page.evaluate("setMetaView('flow'); pbSetUxView('tests');")
            page.wait_for_timeout(300)
            row = lambda key: f'.pb-scan-tr[data-fb-list="tc"][data-key="{key}"]'  # noqa: E731
            txt = lambda sel: (page.locator(sel).first.text_content() or "").strip()  # noqa: E731
            check(errors == [], f"no page errors ({errors[:2]})")
            for w in (1280, 1920):
                page.set_viewport_size({"width": w, "height": 900})
                page.wait_for_timeout(120)
                edges = page.evaluate("""() => { const t = document.querySelector('.pb-scan'), b = document.querySelector('.pb-fbar');
                  const tr = t.getBoundingClientRect(), br = b.getBoundingClientRect(); return [tr.left, tr.right, br.left, br.right]; }""")
                check(abs(edges[1] - edges[3]) <= 2 and abs(edges[0] - edges[2]) <= 2,
                      f"{w}px: the Test Cases list ({edges[0]:.0f}–{edges[1]:.0f}) spans its filter bar ({edges[2]:.0f}–{edges[3]:.0f}), not a narrower column")
            page.set_viewport_size({"width": 1280, "height": 900})
            check(txt(row("s0-0") + " .ti") == "Ward picker offers only wards that have geometry",
                  "a string `test` is the label (it is not cut at its first comma)")
            check(txt(row("s0-1") + " .ti") == "The dropped master is counted, not hidden", "…whole, not at its first delimiter")
            check(txt(row("s1-0") + " .ti") == "Submitting an empty form shows a border AND a message",
                  "`text` is the label, and a long one is cut to its opening claim")
            check(txt(row("s1-1") + " .ti") == "Titled only", "`title` is the label when there is no text or string test")
            check(txt(row("s1-2") + " .ti") == "A bare string: checked by hand", "a bare string is its own label")
            words = {k: txt(row(k) + " .st .w") for k in ("s0-0", "s0-1", "s0-2", "s0-3", "s0-4", "s0-5", "s1-0", "s1-1", "s1-2")}
            check(words == {"s0-0": "Passed", "s0-1": "Retired", "s0-2": "Untested by design", "s0-3": "Not run", "s0-4": "Failed",
                            "s0-5": "Blocked", "s1-0": "Passed", "s1-1": "Not run", "s1-2": "Manual"}, f"every verdict has its words ({words})")
            glyphs = {k: txt(row(k) + " .pb-test-glyph") for k in ("s0-0", "s0-1", "s0-2", "s0-3", "s0-4", "s0-5", "s1-2")}
            check(len(set(glyphs.values())) == len(glyphs), f"…and its own glyph ({glyphs})")
            summary = txt(".pb-test-summary")
            check(summary.startswith("2 pass") and "1 fail" in summary and "1 blocked" in summary and "1 retired" in summary
                  and "1 untested by design" in summary and "2 not run" in summary and "1 manual" in summary
                  and "stale" not in summary, f"the tally counts them, and a `result` pass is not stale ({summary})")
            check(page.evaluate("pbTestCounts()") == {"total": 8, "pass": 2, "fail": 1, "blocked": 1, "retired": 1, "ubd": 1,
                                                       "untested": 2, "stale": 0, "manual": 1}, "pbTestCounts() splits them the same way")
            # a retired case no longer applies: hidden until "Show retired", and N of M counts the live ones
            ret_chip = '.pb-fbar[data-fbar="tc"] [data-pb-quick="archived"]'
            n_rows = page.locator('.pb-scan-tr[data-fb-list="tc"]').count()
            check(page.locator(row("s0-1")).get_attribute("hidden") is not None and "Show retired" in txt(ret_chip)
                  and txt('.pb-fbar[data-fbar="tc"] .pb-fbar-cnt').startswith(f"{n_rows - 1} of {n_rows - 1}"),
                  "a retired case is hidden by default behind a Show retired chip")
            page.locator(ret_chip).click()
            page.wait_for_timeout(80)
            check(page.locator(row("s0-1")).get_attribute("hidden") is None
                  and txt('.pb-fbar[data-fbar="tc"] .pb-fbar-cnt').startswith(f"{n_rows} of {n_rows}"),
                  "Show retired brings it back")
            # one row, then another: both open, with the steps and expectation as written
            page.locator(row("s0-0") + " > .pb-disc-t").click()
            page.locator(row("s0-1") + " > .pb-disc-t").click()
            page.wait_for_timeout(100)
            check(page.locator(row("s0-0") + " .tc-panel").is_visible() and page.locator(row("s0-1") + " .tc-panel").is_visible(),
                  "test cases open together (multi-open)")
            check("Open workspace; open the ward picker" in txt(row("s0-0") + " .tc-panel") and "Every option resolves" in txt(row("s0-0") + " .tc-panel"),
                  "a hand-written case shows its steps and what it expects, as written")
            check("replaced" in txt(row("s0-1") + " .tc-panel") and "Why it is retired" in txt(row("s0-1") + " .tc-panel"),
                  "a retirement's note is shown, headed by why")
            page.locator(row("s1-0") + " > .pb-disc-t").click()
            page.wait_for_timeout(100)
            check("Required" in txt(row("s1-0") + " .tc-panel") and "Click" in txt(row("s1-0") + " .tc-panel"),
                  "a `test{}` block is still said as sentences")
            page.locator(row("s1-2") + " > .pb-disc-t").click()
            page.wait_for_timeout(100)
            check("checked by hand" in txt(row("s1-2") + " .tc-panel"), "a case with no test says it is checked by hand")
            page.locator('.pb-fbar[data-fbar="tc"] [data-pb-chip="result"]').click()
            opts = page.locator('.pb-fbar[data-fbar="tc"] input[data-pb-opt="result"]')
            labels = [opts.nth(i).evaluate("e => e.parentElement.textContent") for i in range(opts.count())]
            check(not any("Retired" in x for x in labels) and any("Untested by design" in x for x in labels),
                  f"the Result filter offers the live verdicts; Retired is the Show retired chip's ({labels})")
            check(not errors, f"zero page errors ({errors[:2]})")
            browser.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if FAIL:
        print("\n✗ %d failure(s)" % len(FAIL))
        sys.exit(1)
    print("\n✓ test cases: both scenario shapes read, every verdict shown")


if __name__ == "__main__":
    main()
