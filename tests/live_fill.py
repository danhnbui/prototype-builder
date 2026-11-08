#!/usr/bin/env python3
"""
live_fill.py — the preview fills in place, one saved line at a time (v2.6), in a real browser.

Boots pb/tools/serve.py on temp copies of the registry template (and of the golden project, for the
case that has screens) and saves lines the way a command does — one `slice.py` call each — asserting:

  1. A save is NOT a navigation: no `load` event, a marker set on `window` survives, the open tab, the
     UX segment and the scroll position are kept, and a boot with no drafts repaints nothing.
  2. Each kind of line lands where it belongs, without a reload: a job on UX Design → Information
     Architecture, a term and a wording on Content, a story and then its scenario (`append`) on Test Cases,
     an ERD row on Data, an objective on Project Summary.
  3. A draft shows a Draft chip, is absent from registry.json, and goes when `slice.py drafts --clear` runs;
     sitemap nodes (`ia.sitemap[]`) draw on the IA tab one node at a time, with a loading node while a
     step is working, and the Prototype tab is an undesigned outline in the device frame, not the empty card.
  4. The server says what kind of change it was: `update` for registry.json / the drafts, `reload` for a
     body file, `activity` for the hook's file; GET /__pb_data returns the registry as the render inlines
     it (no render bodies), the drafts folded in with `_draft`, and the hook's activity.
  5. A body-file change still reloads the page — and the reload comes back on the same tab, segment and scroll.
  6. The progress item: before Search, never a `.meta-tab`, eight steps in order, counts from the registry and
     the drafts, Working / Your turn from the real hook script, Waiting after 90 s without a write, and a
     blue dot on a tab with new content (cleared when it is opened; the page never switches tab itself).
  7. A project with screens has no progress item and a running Prototype session is not reset by a
     `content` write (but a change to a screen still reloads, as it always did); a view-only page has
     neither the item, nor the outline, nor a saved place; the design-system page still reloads.

Dev/CI-only dependency (NS4): pip install playwright && playwright install chromium

Usage:  .venv/bin/python tests/live_fill.py
Exit:   0 = all passed · 1 = a failure · 2 = Playwright/browser not available (a skip: not a pass)
"""
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVE = os.path.join(ROOT, "pb", "tools", "serve.py")
SLICE = os.path.join(ROOT, "pb", "tools", "slice.py")
HOOK = os.path.join(ROOT, "pb", "hooks", "activity.py")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")

_failures = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _failures.append(msg)


class Server:
    """serve.py on a registry; the preview URL is read from its stdout, and it is stopped on exit."""

    def __init__(self, registry):
        self.registry = registry
        self.proc = None
        self.url = None

    def __enter__(self):
        self.proc = subprocess.Popen(
            [sys.executable, SERVE, self.registry, "--no-open", "--host", "127.0.0.1", "--debounce-ms", "60"],
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


def sl(reg, *args, patch=None):
    """One slice.py call — one line saved, exactly as a command does it. Returns its stdout."""
    p = subprocess.run([sys.executable, SLICE, *args, "--registry", reg], input=patch, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if p.returncode != 0:
        raise RuntimeError("slice.py %s failed: %s" % (" ".join(args), p.stderr.strip()))
    return p.stdout


def fresh_project(tmp, jobs=0, view_only=False):
    """A project as /pb:init seeds it: the registry template, the constitution (what makes it a pb project to the
    hook), optionally a screenful of jobs so the IA list can scroll."""
    os.makedirs(os.path.join(tmp, "memory"), exist_ok=True)
    with open(os.path.join(tmp, "memory", "constitution.md"), "w", encoding="utf-8") as f:
        f.write("# constitution\n")
    reg = json.load(open(TEMPLATE, encoding="utf-8"))
    reg["meta"]["name"] = "Live Fill Fixture"
    reg["ia"]["jobs"] = [{"id": "seed%d" % i, "when": "a seeded situation %d" % i, "want": "seeded job %d" % i,
                          "so": "the list is long enough to scroll", "priority": "must", "roles": [], "screens": []}
                         for i in range(jobs)]
    if view_only:
        reg["config"] = {"viewOnly": True}
    path = os.path.join(tmp, "registry.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)
        f.write("\n")
    return path


def golden_project(tmp, view_only=False):
    shutil.copytree(os.path.join(os.path.dirname(GOLDEN), "render"), os.path.join(tmp, "render"))
    os.makedirs(os.path.join(tmp, "memory"), exist_ok=True)
    with open(os.path.join(tmp, "memory", "constitution.md"), "w", encoding="utf-8") as f:
        f.write("# constitution\n")
    reg = json.load(open(GOLDEN, encoding="utf-8"))
    if view_only:
        reg.setdefault("config", {})["viewOnly"] = True
    path = os.path.join(tmp, "registry.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)
        f.write("\n")
    return path, reg


def hook(event, cwd):
    """The real plugin hook, fed what Claude Code feeds it."""
    subprocess.run([sys.executable, "-S", "-B", HOOK], input=json.dumps({"hook_event_name": event, "cwd": cwd}),
                   text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)


def real_console_error(m):
    return m.type == "error" and not ("integrity" in m.text and "mermaid" in m.text)


def offline(page):
    """Nothing but the local preview: the shell pulls Mermaid from a CDN, and this test is about the page."""
    CT = {"script": "application/javascript", "stylesheet": "text/css", "font": "font/woff2", "image": "image/png"}

    def _handle(route):
        url = route.request.url
        if "127.0.0.1" in url or "localhost" in url:
            return route.continue_()
        return route.fulfill(status=200, body="", content_type=CT.get(route.request.resource_type, "text/plain"))
    page.route("**/*", _handle)


def sse_events(base, trigger, want=1, timeout=8.0):
    """Open /__pb_events, run `trigger()`, and return the first `want` `data:` messages (or what arrived in time)."""
    host, port = re.match(r"http://([^:/]+):(\d+)/", base).groups()
    conn = http.client.HTTPConnection(host, int(port), timeout=timeout)
    conn.request("GET", "/__pb_events")
    resp = conn.getresponse()
    got = []

    def read():
        try:
            while len(got) < want:
                line = resp.fp.readline().decode("utf-8", "replace").strip()
                if not line:
                    if resp.isclosed():
                        return
                    continue
                if line.startswith("data:"):
                    got.append(line[5:].strip())
        except Exception:
            return

    t = threading.Thread(target=read, daemon=True)
    t.start()
    time.sleep(0.4)           # the stream is connected and has said `: connected`
    trigger()
    t.join(timeout)
    conn.close()
    return got


def get_json(base, path):
    host, port = re.match(r"http://([^:/]+):(\d+)/", base).groups()
    conn = http.client.HTTPConnection(host, int(port), timeout=10)
    conn.request("GET", path)
    r = conn.getresponse()
    body = r.read()
    conn.close()
    return r.status, json.loads(body.decode("utf-8"))


def run():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed — skipping live_fill (a skip is not a pass).")
        print("  pip install playwright && playwright install chromium")
        sys.exit(2)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            print(f"Could not launch Chromium ({e}). Run: playwright install chromium")
            sys.exit(2)

        def open_page(srv, path=""):
            # Always as a non-Mac browser: the bar's search hint reads "Ctrl K" there, wider than "⌘K",
            # and that width is what pushed the bar's end group over the tabs in CI but never on a Mac.
            page = browser.new_page(viewport={"width": 1280, "height": 720},
                                    user_agent="Mozilla/5.0 (X11; Linux x86_64)")
            page.add_init_script("Object.defineProperty(navigator, 'platform', {get: () => 'Linux x86_64'})")
            offline(page)
            page.errors = []
            page.loads = []
            page.on("console", lambda m: page.errors.append(m.text) if real_console_error(m) else None)
            page.on("pageerror", lambda e: page.errors.append(str(e)))
            page.on("load", lambda *_: page.loads.append(1))
            page.goto(srv.url + path, wait_until="domcontentloaded")
            page.wait_for_selector(".meta-tab" if not path else "body", timeout=10000)
            page.wait_for_load_state("load")
            page.evaluate("window.__pbMarker = 'same-document'")
            return page

        def shown(page, text, within=8000, where="#app"):
            page.wait_for_function("([sel, t]) => (document.querySelector(sel) || {innerText: ''}).innerText.includes(t)",
                                   arg=[where, text], timeout=within)

        def gone(page, text, within=8000, where="#app"):
            page.wait_for_function("([sel, t]) => !(document.querySelector(sel) || {innerText: ''}).innerText.includes(t)",
                                   arg=[where, text], timeout=within)

        def same_document(page):
            return page.evaluate("window.__pbMarker") == "same-document" and len(page.loads) == 1

        # ── a fresh project: the template, filled one line at a time ─────────────────────────────────
        print("a fresh project, filled one line at a time:")
        with tempfile.TemporaryDirectory() as tmp:
            reg = fresh_project(tmp, jobs=40)
            with Server(reg) as srv:
                page = open_page(srv)
                page.evaluate("document.querySelector('#app > *').setAttribute('data-boot-probe', '1')")
                page.wait_for_timeout(1200)
                check(page.evaluate("!!document.querySelector('[data-boot-probe]')"),
                      "a boot with no drafts repaints nothing (/__pb_data agrees with the page it came with)")
                check(page.locator(".meta-tab").count() == 4, "4 tabs, as ever")

                # the user is on UX Design → Information Architecture, scrolled down the job list
                page.click('.meta-tab[data-meta-view="flow"]')
                page.click('.meta-subtab[data-ux-view="ia"]')
                page.wait_for_selector("#ia-scroll .pb-scan-tr", timeout=8000)
                page.evaluate("document.getElementById('ia-scroll').scrollTop = 420")
                page.wait_for_timeout(150)
                top0 = page.evaluate("document.getElementById('ia-scroll').scrollTop")
                check(top0 > 200, f"the job list is scrolled down ({top0}px)")

                # 1 · a job, saved for real
                sl(reg, "set", "ia", "jobs.live1", patch=json.dumps(
                    {"id": "live1", "when": "a quote is requested", "want": "price it in one pass", "so": "the buyer decides today",
                     "priority": "must", "roles": [], "screens": []}))
                shown(page, "Price it in one pass")
                check(same_document(page), "a saved job is not a navigation (no load event, the window marker survived)")
                check(page.evaluate("document.querySelector('.meta-tab.active').dataset.metaView") == "flow"
                      and page.evaluate("document.querySelector('.meta-subtab.active').dataset.uxView") == "ia",
                      "the open tab and the UX segment are kept")
                top1 = page.evaluate("document.getElementById('ia-scroll').scrollTop")
                check(abs(top1 - top0) < 60, f"the scroll position is kept ({top0}px → {top1}px)")
                check(page.locator("#ia-scroll .pb-draft-chip").count() == 0, "an approved job carries no Draft chip")

                # 2 · a draft job: a chip, and not in registry.json
                sl(reg, "set", "ia", "jobs.liveD", "--draft", patch=json.dumps(
                    {"id": "liveD", "when": "the draft is unapproved", "want": "wait for the gate", "so": "nothing is promised",
                     "priority": "should", "roles": [], "screens": []}))
                shown(page, "Wait for the gate")
                check(page.locator("#ia-scroll .pb-scan-tr:has-text('Wait for the gate') .pb-draft-chip").count() == 1,
                      "a draft job shows a Draft chip")
                check("liveD" not in open(reg, encoding="utf-8").read(), "…and is absent from registry.json")
                check(os.path.isfile(os.path.join(tmp, ".preview", "drafts.json")), "…it is in .preview/drafts.json")
                check(same_document(page), "…without a navigation")

                # 3 · sitemap nodes, one at a time (a draft list: the hub has no body yet)
                sl(reg, "set", "ia", "sitemap.n-home", "--draft", patch=json.dumps({"id": "n-home", "name": "Home", "depth": 0}))
                page.wait_for_selector('.ia-node[data-screen="n-home"]', timeout=8000)
                check(page.locator(".ia-node[data-screen]").count() == 1, "the first sitemap node draws alone")
                sl(reg, "set", "ia", "sitemap.n-orders", "--draft", patch=json.dumps(
                    {"id": "n-orders", "name": "Orders", "depth": 1, "parent": "n-home"}))
                page.wait_for_selector('.ia-node[data-screen="n-orders"]', timeout=8000)
                check(page.locator(".ia-node[data-screen]").count() == 2, "the second node arrives on its own, the first stays")
                check(page.locator(".ia-node[data-screen] .pb-draft-chip").count() == 2, "…each carrying the Draft chip")
                check(page.locator("#iamap-stage .ia-edge").count() == 1, "…and the parent → child edge is drawn")
                check(same_document(page), "…still the same document")

                # 4 · the steps menu lives in the activity strip, and the hook
                check(page.locator("#meta-nav #pb-prog").count() == 0 and page.locator(".pb-prog-" + "st").count() == 0,
                      "the bar never carries a progress item")
                check(page.evaluate("document.querySelector('.pb-bar-end').firstElementChild.classList.contains('meta-search')"),
                      "…Search is the first thing in the bar's end")
                check(page.locator("#pb-prog").count() == 0, "…and with no strip yet (the hook has not spoken) there is no steps menu")
                hook("UserPromptSubmit", tmp)
                page.wait_for_selector("#pb-agent #pb-prog-wrap:not([hidden])", timeout=8000)
                check(page.evaluate("!document.getElementById('pb-agent').hidden && document.getElementById('pb-agent').contains(document.getElementById('pb-prog'))"),
                      "UserPromptSubmit → the strip shows and holds the steps button (a project with no screen)")
                check(page.evaluate("!document.querySelector('#pb-prog').classList.contains('meta-tab')") and page.locator(".meta-tab").count() == 4,
                      "…never a .meta-tab (4 tabs still)")
                step0 = page.inner_text("#pb-prog .pb-agent-step")
                check(step0 == "Structure", f"…it names the step the newest line landed in ({step0!r})")
                page.click("#pb-prog")
                check(page.evaluate("!document.getElementById('pb-prog-menu').hidden"), "…clicking it opens the menu")
                check(page.evaluate("document.activeElement === document.querySelector('#pb-prog-menu [data-pb-menu-item]')"),
                      "…focus lands on the first item")
                steps = page.eval_on_selector_all("#pb-prog-menu [data-step]", "els => els.map(e => e.dataset.step)")
                check(steps == ["brief", "ds", "jobs", "structure", "flows", "wording", "data", "screen"],
                      f"…opens a menu of the eight steps, in order ({steps})")
                names = page.eval_on_selector_all("#pb-prog-menu [data-step] span:nth-child(2)", "els => els.map(e => e.textContent)")
                check(names == ["Brief", "Design system", "Jobs and glossary", "Structure", "Flows and test cases", "Wording", "Data", "First screen"],
                      f"…named as the brief names them ({names})")
                counts = dict(zip(steps, page.eval_on_selector_all("#pb-prog-menu .pb-menu-n", "els => els.map(e => +e.textContent)")))
                check(counts["jobs"] == 42 and counts["structure"] == 2 and counts["screen"] == 0,
                      f"…counts come from the registry and the drafts (jobs 42 = 40 seeded + 1 + 1 draft; structure 2): {counts}")
                page.wait_for_timeout(1500)
                check(page.evaluate("!document.getElementById('pb-prog-menu').hidden"), "…the menu stays open across the strip's 1 s ticks")
                page.keyboard.press("Escape")
                check(page.evaluate("document.getElementById('pb-prog-menu').hidden"), "…Escape closes the menu")
                check(page.evaluate("document.activeElement === document.getElementById('pb-prog')"), "…and focus returns to the steps button")

                check(page.evaluate("document.getElementById('pb-agent').dataset.mode") == "working"
                      and page.inner_text("#pb-agent .pb-agent-verb") in ("Thinking", "Writing"),
                      "UserPromptSubmit → mode working, verb Thinking or Writing")
                check(same_document(page), "…and the page was not reloaded for it")
                # while a step is working, the structure step shows a loading node shaped like the next one
                sl(reg, "set", "ia", "sitemap.n-quotes", "--draft", patch=json.dumps(
                    {"id": "n-quotes", "name": "Quotes", "depth": 1, "parent": "n-home"}))
                page.wait_for_selector('.ia-node[data-screen="n-quotes"]', timeout=8000)
                check(page.inner_text("#pb-prog .pb-agent-step") == "Structure",
                      "the step named is the one the newest line landed in")
                check(page.locator(".ia-node--loading").count() == 1, "a loading node shows while the step is working")
                hook("Stop", tmp)
                page.wait_for_function("document.getElementById('pb-agent').dataset.mode === 'turn'", timeout=8000)
                check(page.inner_text("#pb-agent .pb-agent-verb") == "Your turn", "Stop (drafts waiting) → mode turn, verb Your turn")
                page.wait_for_function("document.querySelectorAll('.ia-node--loading').length === 0", timeout=8000)
                check(True, "…and the loading node goes")

                # the 90 s fallback: Stop does not fire on Esc
                with open(os.path.join(tmp, ".preview", "activity.json"), "w", encoding="utf-8") as f:
                    json.dump({"state": "working", "at": time.time() - 87, "event": "UserPromptSubmit"}, f)
                page.wait_for_function("document.getElementById('pb-agent').dataset.mode === 'working'", timeout=8000)
                page.wait_for_function("document.getElementById('pb-agent').dataset.mode === 'waiting'", timeout=12000)
                check(page.inner_text("#pb-agent .pb-agent-verb") == "Waiting", "no write for 90 s → mode waiting, verb Waiting (the fallback for a cancelled turn)")
                with open(os.path.join(tmp, ".preview", "activity.json"), "w", encoding="utf-8") as f:
                    json.dump({"state": "working", "at": time.time() - 200, "event": "UserPromptSubmit"}, f)
                page.wait_for_function("document.getElementById('pb-agent').dataset.mode === 'waiting'", timeout=8000)
                check(True, "…and a 'working' written long ago reads Waiting at once")

                # 5 · the other tabs fill in place
                # Content: a term, then a wording
                page.click('.meta-subtab[data-ux-view="content"]')
                sl(reg, "set", "content", "terms.t-quote", patch=json.dumps(
                    {"id": "t-quote", "term": "Quote", "definition": "a priced offer for one buyer", "aka": [], "avoid": []}))
                shown(page, "a priced offer for one buyer")
                check(page.locator(".ct-term:has-text('Quote')").count() == 1, "a term lands on Content → Definitions")
                page.click(".lg-view:has-text('Wordings')")
                sl(reg, "append", "content", "strings", "--key", "key", patch=json.dumps(
                    {"key": "quote.save", "text": "Save this quote", "kind": "action"}))
                shown(page, "Save this quote")
                check(page.locator(".ct-table tr:has-text('quote.save')").count() == 1, "a wording lands on Content → Wordings (append, no id)")
                sl(reg, "append", "content", "strings", "--key", "key", patch=json.dumps(
                    {"key": "quote.save", "text": "Save this quote", "kind": "action"}))
                page.wait_for_timeout(500)
                check(page.locator(".ct-table tr:has-text('quote.save')").count() == 1, "…and saving the same wording again does not duplicate it (--key)")
                # Test Cases: a story, then its scenario
                page.click('.meta-subtab[data-ux-view="tests"]')
                sl(reg, "set", "flow", "stories.s-quote", patch=json.dumps({"id": "s-quote", "title": "Quote a price", "scenarios": []}))
                sl(reg, "append", "flow", "stories.s-quote.scenarios", patch=json.dumps(
                    {"id": "sc-empty", "text": "Rejects an empty quote"}))
                shown(page, "Rejects an empty quote")
                check(page.locator(".pb-scan-tr[data-fb-list='tc']").count() == 1, "a scenario lands on Test Cases")
                # Data: two rows
                page.click('.meta-tab[data-meta-view="erd"]')
                sl(reg, "append", "erd", "table", patch=json.dumps({"entity": "Quote", "field": "id", "type": "uuid", "example": "q-1"}))
                shown(page, "uuid")
                sl(reg, "append", "erd", "table", patch=json.dumps({"entity": "Quote", "field": "total", "type": "money", "example": "12.50"}))
                shown(page, "money")
                check(page.locator(".erd-entity-table tbody tr").count() == 2, "ERD rows land on Data one at a time (table view before any diagram)")
                # Project Summary: the objective
                page.click('.meta-tab[data-meta-view="summary"]')
                check("No summary yet" in page.inner_text("#app"), "Project Summary starts as its empty state")
                sl(reg, "set", "meta", "overview.objectives", patch=json.dumps("Let a buyer price a job in one pass."))
                shown(page, "Let a buyer price a job in one pass.")
                check(page.locator(".sum-lead").count() == 1, "an objective lands on Project Summary")
                check(same_document(page), "…every one of them in the same document")

                # 6 · a blue dot on a tab with new content; the page never changes tab by itself
                check(page.locator('.meta-tab.has-new').count() == 0, "the tab you are on never carries the dot")
                sl(reg, "set", "ia", "jobs.live2", patch=json.dumps(
                    {"id": "live2", "when": "a second job lands", "want": "tell me where", "so": "I notice", "priority": "could", "roles": [], "screens": []}))
                page.wait_for_selector('.meta-tab[data-meta-view="flow"].has-new', timeout=8000)
                check(page.evaluate("document.querySelector('.meta-tab.active').dataset.metaView") == "summary",
                      "a tab with new content gets a dot — and the page stays on Project Summary")
                check(page.evaluate("getComputedStyle(document.querySelector('.meta-tab[data-meta-view=flow] .pb-tab-dot')).display") == "block",
                      "…the dot is drawn")
                page.click('.meta-tab[data-meta-view="flow"]')
                check(page.locator('.meta-tab.has-new').count() == 0, "opening the tab clears its dot")

                # 7 · the menu jumps to where a step's content lands
                page.click("#pb-prog")
                page.click('#pb-prog-menu [data-step="wording"]')
                check(page.evaluate("state.metaView === 'flow' && state.uxView === 'content' && state.contentView === 'strings'"),
                      "a step in the menu jumps to where its content lands (Wording → Content → Wordings)")
                page.click("#pb-prog")
                page.click('#pb-prog-menu [data-step="data"]')
                check(page.evaluate("state.metaView === 'erd'"), "…Data → the Data tab")

                # 8 · the Prototype tab before any screen
                page.click('.meta-tab[data-meta-view="prototype"]')
                page.wait_for_selector("[data-pb-draft]", timeout=8000)
                check(page.locator(".empty-state").count() == 0, "the Prototype tab is not the empty card")
                check(page.evaluate("!!document.querySelector('.pb-product [data-pb-draft]')"), "…the outline sits inside .pb-product, in the device frame")
                dtxt = page.inner_text("[data-pb-draft]")
                check("Live Fill Fixture" in dtxt and "Let a buyer price a job in one pass." in dtxt,
                      "…it carries the product name and the objective")
                check("Undesigned draft" in dtxt, "…and says it is an undesigned draft")
                check(page.locator(".pb-draft-nav").count() == 3, "…its sidebar is the planned screens (3 sitemap nodes)")
                page.click(".pb-draft-nav:has-text('Orders')")
                check(page.inner_text(".pb-draft-h1") == "Orders", "…a sidebar item can be clicked")
                check("Quote a price" in dtxt and "uuid" in dtxt, "…with the paths and the sample rows once flow and erd exist")
                # a line arriving while the outline is open
                sl(reg, "set", "ia", "sitemap.n-late", "--draft", patch=json.dumps({"id": "n-late", "name": "Late arrival", "depth": 1, "parent": "n-home"}))
                shown(page, "Late arrival", where="[data-pb-draft]")
                check(same_document(page), "…and fills in place too")

                # 9 · drafts clear
                page.click('.meta-tab[data-meta-view="flow"]')
                page.click('.meta-subtab[data-ux-view="ia"]')
                sl(reg, "drafts", "--clear")
                gone(page, "Wait for the gate")
                check(page.locator(".pb-draft-chip").count() == 0, "slice.py drafts --clear removes every Draft chip")
                check(page.locator(".ia-node[data-screen]").count() == 0, "…and the draft sitemap nodes")
                check(same_document(page), "…without a navigation")

                # 10 · a body file changes → the page reloads, and comes back where it was
                page.evaluate("document.getElementById('ia-scroll').scrollTop = 380")
                page.wait_for_timeout(200)
                before = page.evaluate("document.getElementById('ia-scroll').scrollTop")
                os.makedirs(os.path.join(tmp, "render", "components"), exist_ok=True)
                with open(os.path.join(tmp, "render", "components", "probe.js"), "w", encoding="utf-8") as f:
                    f.write("function renderProbe() { return '<p>probe</p>'; }\n")
                page.wait_for_function("window.__pbMarker !== 'same-document'", timeout=10000)
                page.wait_for_selector("#ia-scroll .pb-scan-tr", timeout=10000)
                page.wait_for_timeout(900)
                check(len(page.loads) == 2, f"a body file still reloads the page ({len(page.loads)} loads)")
                check(page.evaluate("document.querySelector('.meta-tab.active').dataset.metaView") == "flow"
                      and page.evaluate("document.querySelector('.meta-subtab.active').dataset.uxView") == "ia",
                      "…and the reload comes back on the same tab and segment")
                after = page.evaluate("document.getElementById('ia-scroll').scrollTop")
                check(abs(after - before) < 80, f"…and the same scroll position ({before}px → {after}px)")
                check(page.evaluate("sessionStorage.getItem('pb:place')") is None, "…the saved place is read once and gone")
                check(not page.errors, f"zero console errors ({page.errors})")
                page.close()

                # the server's own words
                print("the server says what kind of change it was:")
                kinds = sse_events(srv.url, lambda: sl(reg, "set", "ia", "jobs.sse1", patch=json.dumps(
                    {"id": "sse1", "when": "w", "want": "x", "so": "y", "roles": [], "screens": []})))
                check(kinds == ["update"], f"a registry.json write → `update` ({kinds})")
                kinds = sse_events(srv.url, lambda: sl(reg, "set", "ia", "jobs.sse2", "--draft", patch=json.dumps(
                    {"id": "sse2", "when": "w", "want": "x", "so": "y", "roles": [], "screens": []})))
                check(kinds == ["update"], f"a drafts write → `update` ({kinds})")

                def touch_body():
                    with open(os.path.join(tmp, "render", "components", "probe.js"), "a", encoding="utf-8") as f:
                        f.write("// changed\n")
                kinds = sse_events(srv.url, touch_body)
                check(kinds == ["reload"], f"a body file → `reload` ({kinds})")
                kinds = sse_events(srv.url, lambda: hook("UserPromptSubmit", tmp))
                check(kinds == ["activity"], f"the hook's file → `activity` ({kinds})")
                kinds = sse_events(srv.url, lambda: (sl(reg, "set", "ia", "jobs.sse3", patch=json.dumps(
                    {"id": "sse3", "when": "w", "want": "x", "so": "y", "roles": [], "screens": []})), touch_body()), timeout=4)
                check(kinds == ["reload"], f"a registry write and a body write in one burst → `reload`, never `update` ({kinds})")

                status, data = get_json(srv.url, "/__pb_data")
                reg_in = data.get("registry", {})
                check(status == 200 and "registry" in data and "logic" in data and "drafts" in data and "activity" in data,
                      "GET /__pb_data returns registry, logic, drafts and activity")
                check(not any("render" in x or "style" in x for k in ("components", "screens") for x in reg_in.get(k, [])),
                      "…the registry has no render bodies")
                d_jobs = [j for j in reg_in.get("ia", {}).get("jobs", []) if j.get("_draft")]
                check([j["id"] for j in d_jobs] == ["sse2"] and data["drafts"]["count"] >= 1,
                      f"…the drafts are folded in, marked _draft ({[j['id'] for j in d_jobs]})")
                check(data["activity"] and data["activity"]["state"] == "working", "…and the hook's activity rides along")
                on_disk = json.load(open(reg, encoding="utf-8"))
                check(not any(j.get("_draft") or j["id"] == "sse2" for j in on_disk["ia"]["jobs"]), "…while registry.json never holds a draft or a _draft key")

        # ── the activity strip (v2.7): one row under the bar that says what Claude is doing ──────────
        print("the activity strip:")
        with tempfile.TemporaryDirectory() as tmp:
            reg = fresh_project(tmp)
            os.makedirs(os.path.join(tmp, ".preview"), exist_ok=True)
            act_file = os.path.join(tmp, ".preview", "activity.json")
            with Server(reg) as srv:
                page = open_page(srv)
                has_agent = "document.documentElement.classList.contains('pb-has-agent')"
                strip_text = "(document.querySelector('#pb-agent .pb-agent-line') || {innerText: ''}).innerText"

                def write_act(doc):
                    with open(act_file, "w", encoding="utf-8") as f:
                        json.dump(doc, f)

                # a · no activity file → hidden
                check(not os.path.exists(act_file), "no activity file yet")
                check(page.evaluate("document.getElementById('pb-agent').hidden") and not page.evaluate(has_agent),
                      "a · no activity → #pb-agent is hidden and <html> lacks pb-has-agent")

                # b · UserPromptSubmit → Thinking, and the stage gives up a row
                hook("UserPromptSubmit", tmp)
                page.wait_for_function("!document.getElementById('pb-agent').hidden", timeout=8000)
                check(page.evaluate("document.getElementById('pb-agent').dataset.mode") == "working",
                      "b · UserPromptSubmit → #pb-agent is visible with data-mode=working")
                check(page.inner_text("#pb-agent .pb-agent-verb") == "Thinking", "…verb Thinking")
                check(page.evaluate(has_agent), "…<html> has pb-has-agent")
                page.wait_for_function("document.querySelector('.pb-page--viewport') && "
                                       "Math.round(document.querySelector('.pb-page--viewport').getBoundingClientRect().height) === window.innerHeight - 77",
                                       timeout=8000)
                vh = page.evaluate("[Math.round(document.querySelector('.pb-page--viewport').getBoundingClientRect().height), window.innerHeight]")
                check(vh[0] == vh[1] - 77, f"…the Prototype tab's .pb-page--viewport is innerHeight − 77 (44px bar + 33px strip): {vh}")
                check(same_document(page), "…and the page was not reloaded for it")

                # c · a saved line → Writing · step · N saved, with a m:ss clock
                sl(reg, "set", "ia", "sitemap.n-home", "--draft", patch=json.dumps({"id": "n-home", "name": "Home", "depth": 0}))
                page.wait_for_function("document.querySelector('#pb-agent .pb-agent-verb') && document.querySelector('#pb-agent .pb-agent-verb').textContent === 'Writing'", timeout=8000)
                check(True, "c · a saved line → verb Writing")
                line = page.evaluate("document.getElementById('pb-agent').innerText")
                check("Structure" in line and "1 saved" in line, f"…the line names the step and says 1 saved ({line!r})")
                sl(reg, "set", "ia", "sitemap.n-orders", "--draft", patch=json.dumps({"id": "n-orders", "name": "Orders", "depth": 1, "parent": "n-home"}))
                page.wait_for_function(f"({strip_text}).includes('2 saved')", timeout=8000)
                check(True, "…a second line → 2 saved")
                clock = page.inner_text("#pb-agent .pb-agent-time")
                check(re.match(r"^\d+:\d\d$", clock) is not None, f"…the clock reads m:ss ({clock!r})")

                # d · Stop with drafts waiting → Your turn, N drafts to approve
                hook("Stop", tmp)
                page.wait_for_function("document.getElementById('pb-agent').dataset.mode === 'turn'", timeout=8000)
                check(page.inner_text("#pb-agent .pb-agent-verb") == "Your turn", "d · Stop with drafts → data-mode=turn, verb Your turn")
                check("drafts to approve" in page.evaluate(strip_text), f"…{page.evaluate(strip_text)!r} says how many drafts wait")
                check(page.inner_text("#pb-agent .pb-agent-time").startswith("Waiting "), "…the clock reads Waiting m:ss")

                # e · Stop with nothing to approve → done, and how long the turn took
                sl(reg, "drafts", "--clear")
                page.wait_for_function("document.getElementById('pb-agent').dataset.mode === 'done'", timeout=8000)
                check("Claude finished this turn" in page.evaluate(strip_text), "e · drafts cleared → data-mode=done, 'Claude finished this turn'")
                check(page.inner_text("#pb-agent .pb-agent-time").startswith("in "),
                      f"…the clock says how long the turn took ({page.inner_text('#pb-agent .pb-agent-time')!r})")

                # g · a content write neither resets nor removes the strip
                hook("UserPromptSubmit", tmp)
                page.wait_for_function("document.getElementById('pb-agent').dataset.mode === 'working'", timeout=8000)
                sl(reg, "set", "content", "terms.t-strip", patch=json.dumps(
                    {"id": "t-strip", "term": "Strip", "definition": "the row that says what Claude is doing", "aka": [], "avoid": []}))
                page.wait_for_selector('.meta-tab[data-meta-view="flow"].has-new', timeout=8000)
                check(not page.evaluate("document.getElementById('pb-agent').hidden") and page.evaluate(has_agent)
                      and page.evaluate("document.getElementById('pb-agent').dataset.mode") == "working",
                      "g · a content write does not remove or reset the strip")
                check(same_document(page), "…no navigation either")

                # h · one live region, and no fifth tab
                check(page.locator('#pb-agent [role="status"]').count() == 1, "h · exactly one role=status inside #pb-agent")
                check(page.locator(".meta-tab").count() == 4, "…the strip adds no fifth .meta-tab")

                # f · the 90 s fallback, then a session that has gone cold
                write_act({"state": "working", "at": time.time() - 100, "event": "UserPromptSubmit"})
                page.wait_for_function("document.getElementById('pb-agent').dataset.mode === 'waiting'", timeout=8000)
                check(page.inner_text("#pb-agent .pb-agent-verb") == "Waiting", "f · working but silent for 100 s → data-mode=waiting, verb Waiting")
                write_act({"state": "idle", "at": time.time() - 2000, "event": "Stop"})
                page.wait_for_function("document.getElementById('pb-agent').hidden", timeout=8000)
                check(not page.evaluate(has_agent), "…an idle session older than 30 min → hidden again, pb-has-agent removed")
                check(not page.errors, f"zero console errors ({page.errors})")
                page.close()

        # ── the same page, a second tab type: the design-system page keeps reloading as before ──────
        print("the design-system page:")
        with tempfile.TemporaryDirectory() as tmp:
            reg, gold = golden_project(tmp)
            with Server(reg) as srv:
                ds = open_page(srv, "design-system")
                ds.wait_for_function("document.readyState === 'complete'", timeout=10000)
                n0 = len(ds.loads)
                sl(reg, "set", "content", "terms.ds-probe", "--create-list", patch=json.dumps(
                    {"id": "ds-probe", "term": "Probe", "definition": "a line saved while the design system is open"}))
                ds.wait_for_function("window.__pbMarker !== 'same-document'", timeout=10000)
                check(len(ds.loads) == n0 + 1, "a data update reloads the design-system page, as it always did (it has no pbApplyData)")
                ds.close()

        # ── a project with screens ───────────────────────────────────────────────────────────────────
        print("a project with screens:")
        with tempfile.TemporaryDirectory() as tmp:
            reg, gold = golden_project(tmp)
            first_screen = gold["screens"][0]["id"]
            with Server(reg) as srv:
                page = open_page(srv)
                check(page.locator("#meta-nav #pb-prog").count() == 0 and page.locator(".pb-prog-" + "st").count() == 0,
                      "a project with screens has no progress item in the bar")
                check(page.locator(".meta-tab").count() == 4, "…4 tabs")
                page.wait_for_selector("#proto-frame .field__input", timeout=10000)
                page.locator("#proto-frame .field__input").nth(0).fill("typed-by-test@example.com")
                sl(reg, "set", "content", "terms.keep-session", "--create-list", patch=json.dumps(
                    {"id": "keep-session", "term": "Session", "definition": "what a running prototype holds"}))
                page.wait_for_selector('.meta-tab[data-meta-view="flow"].has-new', timeout=8000)
                check(same_document(page), "a content write does not navigate a running Prototype session")
                check(page.locator("#proto-frame .field__input").nth(0).input_value() == "typed-by-test@example.com",
                      "…and the field the reader typed in is still filled (the prototype was not repainted)")
                check(page.evaluate("document.querySelector('.meta-tab.active').dataset.metaView") == "prototype",
                      "…the Prototype tab stays; the UX Design tab gets the dot instead")
                # the activity strip shows on a project with screens too, and the running session is left alone
                hook("UserPromptSubmit", tmp)
                page.wait_for_function("!document.getElementById('pb-agent').hidden", timeout=8000)
                check(page.evaluate("document.getElementById('pb-agent').dataset.mode") == "working"
                      and page.evaluate("document.documentElement.classList.contains('pb-has-agent')"),
                      "g · a project with screens shows the activity strip too")
                check(same_document(page) and page.locator("#proto-frame .field__input").nth(0).input_value() == "typed-by-test@example.com",
                      "…and it does not touch the running Prototype session")
                check(page.evaluate("(() => { const w = document.getElementById('pb-prog-wrap'); return !w || w.hidden; })()"),
                      "…but it has no steps menu (a project with screens)")
                check(page.evaluate("(() => { const t = document.querySelector('#pb-agent .pb-agent-steptxt'); return !t || t.hidden; })()"),
                      "…and no step words until a line lands this turn")
                sl(reg, "set", "screens", first_screen, patch=json.dumps({"name": "Renamed by the test"}))
                page.wait_for_function("window.__pbMarker !== 'same-document'", timeout=10000)
                page.wait_for_selector(".meta-tab", timeout=10000)
                check(len(page.loads) == 2, "a change to a screen under a running session is a real reload, as today")
                check(page.evaluate("document.querySelector('.meta-tab.active').dataset.metaView") == "prototype", "…back on the Prototype tab")
                check(not page.errors, f"zero console errors ({page.errors})")
                page.close()

        # ── view-only ─────────────────────────────────────────────────────────────────────────────────
        print("a view-only page:")
        with tempfile.TemporaryDirectory() as tmp:
            reg = fresh_project(tmp, view_only=True)
            with Server(reg) as srv:
                page = open_page(srv)
                check(page.evaluate("document.body.classList.contains('view-only')"), "the page is view-only")
                check(page.locator("#pb-prog").count() == 0 and page.locator(".pb-prog-" + "st").count() == 0,
                      "no progress item on a view-only page")
                os.makedirs(os.path.join(tmp, ".preview"), exist_ok=True)
                hook("UserPromptSubmit", tmp)
                _, adata = get_json(srv.url, "/__pb_data")
                check(adata.get("activity") and adata["activity"].get("state") == "working", "…the server does see the hook's activity")
                page.wait_for_timeout(1800)
                check(page.evaluate("document.getElementById('pb-agent').hidden") and
                      not page.evaluate("document.documentElement.classList.contains('pb-has-agent')"),
                      "g · a view-only page never shows the activity strip")
                check(page.locator("#pb-prog").count() == 0, "…nor a steps menu")
                check(page.locator(".meta-tab").count() == 4, "…4 tabs")
                check(page.locator("[data-pb-draft]").count() == 0 and page.locator(".empty-state").count() == 1,
                      "…the Prototype tab keeps the plain empty state, not the outline")
                page.evaluate("pbSavePlace()")
                check(page.evaluate("sessionStorage.getItem('pb:place')") is None, "…and no place is saved")
                page.close()

        # ── an ordinary page saves its place only over http and only when asked ─────────────────────
        print("keeping a place:")
        with tempfile.TemporaryDirectory() as tmp:
            reg = fresh_project(tmp, jobs=3)
            with Server(reg) as srv:
                page = open_page(srv)
                page.click('.meta-tab[data-meta-view="erd"]')
                check(page.evaluate("sessionStorage.getItem('pb:place')") is None, "nothing is stored while you read")
                page.evaluate("pbSavePlace()")
                saved = json.loads(page.evaluate("sessionStorage.getItem('pb:place')"))
                check(saved["view"] == "erd", f"pbSavePlace() keeps the tab ({saved['view']})")
                page.evaluate("sessionStorage.setItem('pb:place', JSON.stringify(Object.assign({}, JSON.parse(sessionStorage.getItem('pb:place')), {t: Date.now() - 60000})))")
                page.reload(wait_until="domcontentloaded")
                page.wait_for_selector(".meta-tab", timeout=10000)
                check(page.evaluate("document.querySelector('.meta-tab.active').dataset.metaView") == "prototype",
                      "a place older than 20 s is not returned to")
                page.close()
        browser.close()

    print()
    if _failures:
        print(f"FAIL — {len(_failures)} check(s) failed:")
        for m in _failures:
            print("  -", m)
        sys.exit(1)
    print("PASS — live_fill: the preview fills in place, one line at a time")


if __name__ == "__main__":
    run()
